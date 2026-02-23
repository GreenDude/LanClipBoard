from fastapi import FastAPI
from clipboard_storage import ClipboardEntry
app = FastAPI()


entries = []

@app.post("/clipboard_entry")
async def clipboard_entry(entry: ClipboardEntry):
    entries.append(entry.model_dump())

    for e in entries:
        print(e)

    return {"platform": entry.platform, "entry": entry.entry, "timestamp": entry.timestamp}