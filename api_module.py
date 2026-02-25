from fastapi import Request, APIRouter
from fastapi.params import Depends

from clipboard_storage import ClipboardEntry, ClipboardStorage

def get_storage(request: Request) -> ClipboardStorage:
    return request.app.state.clipboard_storage


def build_rest_router():
    rest_router = APIRouter(prefix="/api", tags=["api"])

    @rest_router.post("/clipboard_entry")
    async def post_clipboard_entry(
            entry: ClipboardEntry,
            request: Request,
            cs: ClipboardStorage = Depends(get_storage)
    ):

        if cs.store_clipboard_entry(request.client.host, entry):
            return {"host": request.client.host, "platform": entry.platform, "entry": entry.entry,
                    "timestamp": entry.timestamp}
        else:
            return {
                f"failed to process type: {entry.type}, entry: {entry.entry}, timestamp: {entry.timestamp}, platform: {entry.platform}"}

    @rest_router.get("/clipboard_entries")
    async def get_clipboard_entries(cs: ClipboardStorage = Depends(get_storage)):
        entries = cs.get_all_clipboard_entries()
        return {"entries": entries or []}

    @rest_router.get("/clipboard_entries/latest")
    async def get_clipboard_entry(cs: ClipboardStorage = Depends(get_storage)):

        return cs.get_latest_clipboard_entry() if cs.get_latest_clipboard_entry() else None

    return rest_router