from typing import List

import aiofiles
import httpx
from fastapi import Request, APIRouter, responses
from fastapi.params import Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

from starlette.responses import StreamingResponse

from clipboard_storage import ClipboardEntry, ClipboardStorage


class FileRequest(BaseModel):
    path: str

    def set_path(self, path: str):
        self.path = path
        return self

CHUNK_SIZE = 1024 * 1024  # 1 MB


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

        entry_origin = request.client.host
        entry.origin = entry_origin

        if cs.store_clipboard_entry(entry_origin, entry):
            return {"host": request.client.host, "platform": entry.platform, "entry": entry.entry,
                    "timestamp": entry.timestamp}
        else:
            return {
                f"failed to process type: {entry.type}, entry: {entry.entry}, timestamp: {entry.timestamp}, platform: {entry.platform}"
            }

    @rest_router.get("/clipboard_entries")
    async def get_clipboard_entries(cs: ClipboardStorage = Depends(get_storage)):
        entries = cs.get_all_clipboard_entries()
        return {"entries": entries or []}

    @rest_router.get("/clipboard_entries/latest")
    async def get_clipboard_entry(cs: ClipboardStorage = Depends(get_storage)):

        return cs.get_latest_clipboard_entry() if cs.get_latest_clipboard_entry() else None

    @rest_router.post("/file")
    async def get_file(file_request: FileRequest):
        file_path = Path(file_request.path)

        async def iter_file():
            async with aiofiles.open(file_path, "rb") as f:
                while chunk := await f.read(CHUNK_SIZE):
                    yield chunk

        headers = {
            "Content-Disposition": f'attachment; filename="{file_path.name}"'
        }

        return StreamingResponse(
            iter_file(),
            headers=headers,
            media_type="application/octet-stream"
        )

    return rest_router


def broadcast_to_peers(entry: ClipboardEntry, peers: list[str], port: int = 8000) -> None:
    payload = entry.model_dump(mode="json")  # datetime -> ISO string

    with httpx.Client(timeout=2) as client:
        for ip in peers:
            url = f"http://{ip}:{port}/api/clipboard_entry"
            try:
                r = client.post(url, json=payload)
                r.raise_for_status()
            except Exception as e:
                print(f"[broadcast] failed to send to {ip}: {e}")


def get_files(paths: List[str], ip: str, port: int = 8000):

    timeout = httpx.Timeout(connect=5, read=60, write = 30, pool = 5)
    url = f"http://{ip}:{port}/api/file"

    with httpx.Client(timeout=timeout) as client:
        try :
            for str_path in paths:
                file_path = Path(str_path)
                file_name = file_path.name
                json_body = FileRequest(path=str_path)
                payload = json_body.model_dump(mode="json")

                with client.stream("POST", url, json=payload) as r:

                    r.raise_for_status()
                    temp_file = file_name
                    print(f"Saving {file_name} to temp_file")

                    with open(file_name, "wb") as f:
                        chunk_num = 0
                        for chunk in r.iter_bytes(chunk_size=CHUNK_SIZE):
                            chunk_num += 1
                            print(f"Saving chunk # {chunk_num}")
                            f.write(chunk)
                        print(f"File {file_name} saved")


        except Exception as e:
            print(f"[file request] failed to receive from {ip}: {e}")
