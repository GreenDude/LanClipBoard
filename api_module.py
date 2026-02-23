from fastapi import FastAPI
from pydantic import BaseModel


class ClipboardEntry(BaseModel):
    platform: str
    type: str
    entry: str
    timestamp: str

app = FastAPI()


entries = []

@app.post("/clipboard_entry")
async def clipboard_entry(entry: ClipboardEntry):
    entries.append(entry.model_dump())

    for e in entries:
        print(e)

    return {"platform": entry.platform, "entry": entry.entry, "timestamp": entry.timestamp}