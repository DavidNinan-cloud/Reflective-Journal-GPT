from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables
load_dotenv()

# Configuration

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

# NOTION_TOKEN = os.getenv("NOTION_TOKEN")
# DATABASE_ID = os.getenv("DATABASE_ID")s
# # Format: postgresql://username:password@localhost:5432/logicmap_db
# DATABASE_URL = os.getenv("DATABASE_URL")

if not NOTION_TOKEN or not DATABASE_ID or not DATABASE_URL:
    raise ValueError("Missing environment variables: NOTION_TOKEN, DATABASE_ID, or DATABASE_URL.")

# ----- PostgreSQL Database Setup -----
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DocEntry(Base):
    __tablename__ = "software_docs"
    
    id = Column(Integer, primary_key=True, index=True)
    notion_page_id = Column(String(255), unique=True, nullable=False)
    notion_database_id = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    summary = Column(Text)
    code_details = Column(Text)
    project_status = Column(String(50))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create the table if it doesn't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="LogicMap: Software Documentation API")

# ----- Notion API setup -----
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def create_notion_doc(title, summary, code_details, project_status):
    """Creates a page in Notion and mirrors the entry to PostgreSQL."""
    print(f"🚀 Processing documentation entry: {title}")
    
    create_url = "https://api.notion.com/v1/pages"

    # 1. Prepare data for Notion
    new_page_data = {
        "parent": { "database_id": DATABASE_ID },
        "properties": {
            "Title": {"title": [{"text": {"content": title}}]},
            "Summary": {"rich_text": [{"text": {"content": summary}}]},
            "Code Details": {"rich_text": [{"text": {"content": code_details}}]},
            "Project Status": {"select": {"name": project_status}}
        }
    }

    # 2. Send to Notion
    response = requests.post(create_url, headers=headers, json=new_page_data)

    if response.status_code in [200, 201]:
        notion_res = response.json()
        page_id = notion_res.get("id")
        
        # 2. Immediately Update the page with its own ID
        update_url = f"https://api.notion.com/v1/pages/{page_id}"
        update_data = {
            "properties": {
                "Page ID": {"rich_text": [{"text": {"content": page_id}}]}
            }
        }
        requests.patch(update_url, headers=headers, json=update_data)

        # 3. Mirror to local PostgreSQL
        db = SessionLocal()
        try:
            new_record = DocEntry(
                notion_page_id=page_id,
                notion_database_id=DATABASE_ID,
                title=title,
                summary=summary,
                code_details=code_details,
                project_status=project_status
            )
            db.add(new_record)
            db.commit()
            print("✅ Successfully mirrored to PostgreSQL.")
        except Exception as e:
            print(f"⚠️ Mirroring error: {e}")
            db.rollback()
        finally:
            db.close()

        return {"message": "Success", "notion_page_id": page_id}
    else:
        print(f"❌ Notion Error: {response.status_code} - {response.text}")
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Notion API failed: {response.text}"
        )



# ----- FastAPI model -----
class SoftwareDocEntry(BaseModel):
    title: str
    summary: str
    code_details: str
    project_status: str

# ----- FastAPI routes -----

@app.get("/")
def read_root():
    return {"message": "LogicMap API is active and mirroring to PostgreSQL."}



@app.get("/search_logic")
def search_logic(query: str):
    """GPT route to find logic in PGsql and return a direct Notion link."""
    db = SessionLocal()
    # Searches for keywords in title, summary, or code_details
    try:
        results = db.query(DocEntry).filter(
            DocEntry.title.ilike(f"%{query}%") | 
            DocEntry.summary.ilike(f"%{query}%") |
            DocEntry.code_details.ilike(f"%{query}%") |
            DocEntry.project_status.ilike(f"%{query}%")
        ).all()
        db.close()

        formatted = []
        for r in results:
            
            # print("results",r)
            # Notion IDs in URLs should not have dashes
            clean_id = r.notion_page_id.replace("-", "")
            formatted.append({
                "title": r.title,
                "notion_url": f"https://notion.so/{clean_id}",
                "status": r.project_status,
                "created_at": r.created_at
            })
        return {"matches": formatted}
        
    except Exception as e:
        print(f"❌ Search Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Search Error")
    finally:
        db.close()


@app.post("/create_documentation")
def post_docs(entry: SoftwareDocEntry):
    allowed_statuses = ["Development", "Testing", "Stable", "Blocked", "Deprioritized"]
    if entry.project_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Invalid status provided.")

    return create_notion_doc(
        title=entry.title,
        summary=entry.summary,
        code_details=entry.code_details,
        project_status=entry.project_status
    )

@app.post("/sync_databases")
def sync_notion_to_pgsql():
    """
    1. Fetches all active pages from Notion.
    2. Updates/Creates them in PostgreSQL.
    3. Deletes rows from PostgreSQL if they no longer exist in Notion.
    """
    print("🔄 Starting full database synchronization...")
    query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    
    # 1. Fetch all active pages from Notion
    response = requests.post(query_url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch from Notion")
    
    notion_pages = response.json().get("results", [])
    active_notion_ids = [page["id"] for page in notion_pages] # Collect active IDs
    
    db = SessionLocal()
    try:
        # 2. Update or Create logic
        for page in notion_pages:
            p_id = page["id"]
            props = page["properties"]
            
            # Helper to extract text safely (handles empty fields)
            title = props.get("Title", {}).get("title", [{}])[0].get("text", {}).get("content", "Untitled")
            
            summary_list = props.get("Summary", {}).get("rich_text", [])
            summary_text = summary_list[0]["text"]["content"] if summary_list else ""
            
            code_list = props.get("Code Details", {}).get("rich_text", [])
            code_text = code_list[0]["text"]["content"] if code_list else ""
            
            status = props.get("Project Status", {}).get("select", {}).get("name", "Development")

            existing = db.query(DocEntry).filter(DocEntry.notion_page_id == p_id).first()
            if existing:
                existing.title = title
                existing.summary = summary_text
                existing.code_details = code_text
                existing.project_status = status
            else:
                new_entry = DocEntry(
                    notion_page_id=p_id,
                    notion_database_id=DATABASE_ID,
                    title=title,
                    summary=summary_text,
                    code_details=code_text,
                    project_status=status
                )
                db.add(new_entry)

        # 3. DELETE rows from PGSQL that are NOT in the active_notion_ids list
        deleted_count = db.query(DocEntry).filter(~DocEntry.notion_page_id.in_(active_notion_ids)).delete(synchronize_session=False)
        
        db.commit()
        print(f"✅ Sync complete. Updated {len(active_notion_ids)} items. Pruned {deleted_count} deleted items.")
        return {
            "status": "Sync Complete",
            "active_items": len(active_notion_ids),
            "pruned_items": deleted_count
        }

    except Exception as e:
        db.rollback()
        print(f"❌ Sync Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.patch("/update_documentation/{page_id}")
def update_docs(page_id: str, entry: SoftwareDocEntry):
    """Updates an existing Notion page and synchronizes the change to PGSQL."""
    
    # 1. Update Notion
    update_url = f"https://api.notion.com/v1/pages/{page_id}"
    update_data = {
        "properties": {
            "Title": {"title": [{"text": {"content": entry.title}}]},
            "Summary": {"rich_text": [{"text": {"content": entry.summary}}]},
            "Code Details": {"rich_text": [{"text": {"content": entry.code_details}}]},
            "Project Status": {"select": {"name": entry.project_status}}
        }
    }
    
    response = requests.patch(update_url, headers=headers, json=update_data)
    
    if response.status_code == 200:
        # 2. Update Local PostgreSQL
        db = SessionLocal()
        try:
            existing_record = db.query(DocEntry).filter(DocEntry.notion_page_id == page_id).first()
            if existing_record:
                existing_record.title = entry.title
                existing_record.summary = entry.summary
                existing_record.code_details = entry.code_details
                existing_record.project_status = entry.project_status
                # updated_at is handled automatically by SQLAlchemy 'onupdate'
                db.commit()
                print(f"✅ PGSQL mirrored update for page: {page_id}")
            else:
                print(f"⚠️ Page {page_id} found in Notion but missing in local PGSQL.")
        except Exception as e:
            print(f"❌ DB Sync Error: {e}")
            db.rollback()
        finally:
            db.close()
            
        return {"message": "Update successful in both Notion and PGSQL"}
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Notion Update Failed: {response.text}")
    






if __name__ == "__main__":
    import uvicorn
    # Render provides a $PORT environment variable automatically
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)