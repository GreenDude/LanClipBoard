from fastapi import Request, APIRouter
from clipboard_storage import ClipboardEntry, ClipboardStorage

rest_router = APIRouter(prefix="/api", tags=["api"])

cs = ClipboardStorage()

@rest_router.post("/clipboard_entry")
async def post_clipboard_entry(entry: ClipboardEntry, request: Request):

    if cs.store_clipboard_entry(request.client.host, entry):
        return {"host": request.client.host, "platform": entry.platform, "entry": entry.entry, "timestamp": entry.timestamp}
    else:
        return {f"failed to process type: {entry.type}, entry: {entry.entry}, timestamp: {entry.timestamp}, platform: {entry.platform}"}

@rest_router.get("/clipboard_entries")
async def get_clipboard_entries():

    if cs.get_all_clipboard_entries():
        return {"entries": cs.get_all_clipboard_entries()}
    else: return {"entries": []}


@rest_router.get("/clipboard_entries/latest")
async def get_clipboard_entry():

    return cs.get_latest_clipboard_entry() if cs.get_latest_clipboard_entry() else None