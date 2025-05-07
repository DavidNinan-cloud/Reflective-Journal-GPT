from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import requests
import os
from dotenv import load_dotenv

# Load environment variables (Render will provide these at runtime)
load_dotenv()

# Load environment variables (Render will provide these at runtime)
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_TOKEN or not DATABASE_ID:
    raise ValueError("NOTION_TOKEN and DATABASE_ID must be set as environment variables.")

app = FastAPI()

# ----- Notion API setup -----

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}


def create_journal_entry(date, title, entry, grammar_fixes, emotional_state):
    create_url = "https://api.notion.com/v1/pages"

    new_page_data = {
        "parent": { "database_id": DATABASE_ID },
        "properties": {
            "Entries": {  # Title property
                "title": [{ "text": { "content": title } }]
            },
            "Date": {
                "date": { "start": date }
            },
            "Entry": {
                "rich_text": [{ "text": { "content": entry } }]
            },
            "Grammer Fixes": {
                "rich_text": [{ "text": { "content": grammar_fixes } }]
            },
            "Emotional State": {
                "select": { "name": emotional_state }
            }
        }
    }

    response = requests.post(create_url, headers=headers, json=new_page_data)
    if response.status_code in [200, 201]:
        print("✅ Journal entry created successfully.")
    else:
        print("❌ Failed to create entry:", response.status_code, response.text)

# Example usage
create_journal_entry(
    date="2025-05-05",
    title="Render test 1 - First Successful API Entry",
    entry="Testing 1 I finally got the Notion integration to work perfectly through Colab.",
    grammar_fixes="No major issues.",
    emotional_state="Motivated"
)


# ----- FastAPI model -----

class JournalEntry(BaseModel):
    date: str
    title: str
    entry: str
    grammar_fixes: str
    emotional_state: str

# ----- FastAPI routes -----

@app.get("/")
def read_root():
    return {"message": "Reflective Journal GPT API is running with validation!"}

@app.post("/create_journal_entry")
def post_journal(entry: JournalEntry):
    allowed_states = ["Motivated", "Happy", "Neutral", "Sad", "Tired"]
    if entry.emotional_state not in allowed_states:
        raise HTTPException(
            status_code=400,
            detail=f"Emotional State must be one of: {', '.join(allowed_states)}"
        )

    response = create_journal_entry(
        date=entry.date,
        title=entry.title,
        entry=entry.entry,
        grammar_fixes=entry.grammar_fixes,
        emotional_state=entry.emotional_state
    )

    if response.status_code in [200, 201]:
        return {"message": "✅ Journal entry created successfully."}
    else:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to create entry. Notion response: {response.text}"
        )




# @app.post("/create_journal_entry")
# def post_journal(entry: create_journal_entry):
#     allowed_states = ["Motivated", "Happy", "Neutral", "Sad", "Tired"]
#     if entry.emotional_state not in allowed_states:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Emotional State must be one of: {', '.join(allowed_states)}"
#         )

#     response = create_journal_entry(
#         date=entry.date,
#         title=entry.title,
#         entry=entry.entry,
#         grammar_fixes=entry.grammar_fixes,
#         emotional_state=entry.emotional_state
#     )

#     if response.status_code in [200, 201]:
#         return {"message": "✅ Journal entry created successfully."}
#     else:
#         raise HTTPException(
#             status_code=response.status_code,
#             detail=f"Failed to create entry. Notion response: {response.text}"
#         )

# @app.get("/")
# def read_root():
#     return {"message": "Reflective Journal GPT API is running with validation!"}


# @app.post("/create_journal_entry")
# def post_journal(entry: JournalEntry):
    allowed_states = ["Motivated", "Happy", "Neutral", "Sad", "Tired"]  # Match your Notion options
    if entry.emotional_state not in allowed_states:
        raise HTTPException(
            status_code=400,
            detail=f"Emotional State must be one of: {', '.join(allowed_states)}"
        )

    response = create_journal_entry(
        date=entry.date,
        title=entry.title,
        entry=entry.entry,
        grammar_fixes=entry.grammar_fixes,
        emotional_state=entry.emotional_state
    )

    if response.status_code in [200, 201]:
        return {"message": "✅ Journal entry created successfully."}
    else:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to create entry. Notion response: {response.text}"
        )