from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration (Uses .env file; defaults provided as fallback)
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

if not NOTION_TOKEN or not DATABASE_ID:
    raise ValueError("NOTION_TOKEN and DATABASE_ID must be set as environment variables.")

app = FastAPI(title="Software Documentation GPT API")

# ----- Notion API setup -----

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def create_notion_doc(date, title, summary, code_fixes, project_status):
    """Sends documentation data to the Notion API."""
    print(f"🚀 Creating documentation entry: {title}")
    
    create_url = "https://api.notion.com/v1/pages"

    new_page_data = {
        "parent": { "database_id": DATABASE_ID },
        "properties": {
            "Title": {
                "title": [{ "text": { "content": title } }]
            },
            "Date": {
                "date": { "start": date }
            },
            "Summary": {
                "rich_text": [{ "text": { "content": summary } }]
            },
            "Code Fixes": {
                "rich_text": [{ "text": { "content": code_fixes } }]
            },
            "Project Status": {
                "select": { "name": project_status }
            }
        }
    }

    response = requests.post(create_url, headers=headers, json=new_page_data)

    if response.status_code in [200, 201]:
        print("✅ Documentation created successfully.")
        return {"message": "✅ Documentation created successfully."}
    else:
        print(f"❌ Notion Error: {response.status_code} - {response.text}")
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to create entry. Notion response: {response.text}"
        )

# ----- FastAPI model -----

class SoftwareDocEntry(BaseModel):
    date: str
    title: str
    summary: str
    code_fixes: str
    project_status: str

# ----- FastAPI routes -----

@app.get("/")
def read_root():
    return {"message": "Software Documentation API is running!"}

@app.post("/create_documentation")
def post_docs(entry: SoftwareDocEntry):
    # Suggested software-specific status validations
    allowed_statuses = ["Development", "Testing", "Stable", "Blocked", "Deprioritized"]
    
    if entry.project_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Project Status must be one of: {', '.join(allowed_statuses)}"
        )

    result = create_notion_doc(
        date=entry.date,
        title=entry.title,
        summary=entry.summary,
        code_fixes=entry.code_fixes,
        project_status=entry.project_status
    )

    return result