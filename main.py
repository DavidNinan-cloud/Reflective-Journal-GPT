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
    results = db.query(DocEntry).filter(
        DocEntry.title.ilike(f"%{query}%") | 
        DocEntry.summary.ilike(f"%{query}%") |
        DocEntry.code_details.ilike(f"%{query}%")
    ).all()
    db.close()

    formatted = []
    for r in results:
        # Notion IDs in URLs should not have dashes
        clean_id = r.notion_page_id.replace("-", "")
        formatted.append({
            "title": r.title,
            "notion_url": f"https://notion.so/{clean_id}",
            "status": r.project_status,
            "created_at": r.created_at
        })
    return {"matches": formatted}



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
    """Fetches all entries from Notion and updates local PGsql if they differ."""
    query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    res = requests.post(query_url, headers=headers)
    pages = res.json().get("results", [])

    db = SessionLocal()
    for page in pages:
        p_id = page["id"]
        props = page["properties"]
        
        # Extract the current values from Notion
        title = props["Title"]["title"][0]["text"]["content"]
        status = props["Project Status"]["select"]["name"]
        
        # Update or Create in PostgreSQL
        existing = db.query(DocEntry).filter(DocEntry.notion_page_id == p_id).first()
        if existing:
            existing.title = title
            existing.project_status = status
        else:
            # Add if it's a completely new page created manually in Notion
            print('props',props)
            new_entry = DocEntry(
                notion_page_id=p_id,
                notion_database_id=DATABASE_ID,
                title=title,
                summary= props["Summary"]["rich_text"][0]["text"]["content"],
                code_details= props["Code Details"]["rich_text"][0]["text"]["content"],
                project_status=status
            )
            db.add(new_entry)
            
    db.commit()
    db.close()
    return {"message": "Sync complete"}