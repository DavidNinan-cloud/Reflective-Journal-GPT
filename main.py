from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import requests
import os
from dotenv import load_dotenv

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


def create_journal_entry(date, entry, grammar_fixes, emotional_state):
    create_url = "https://api.notion.com/v1/pages"

    new_page_data = {
        "parent": { "database_id": DATABASE_ID },
        "properties": {
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
                "rich_text": [{ "text": { "content": emotional_state } }]
            }
        }
    }

    response = requests.post(create_url, headers=headers, json=new_page_data)
    if response.status_code == 200 or response.status_code == 201:
        print("Journal entry created successfully.")
    else:
        print("Failed to create entry:", response.status_code, response.text)

# Example usage
create_journal_entry(
    date="2025-05-05",
    entry="Today I set up my Notion integration!",
    grammar_fixes="No issues found.",
    emotional_state="Excited"
)
