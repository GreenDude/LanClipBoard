import socket
from queue import Queue
from typing import List
from urllib.parse import quote

import aiofiles
import httpx
from fastapi import Request, APIRouter, responses
from fastapi.params import Depends
from pydantic import BaseModel
from pathlib import Path

from starlette.responses import StreamingResponse

from clipboard_storage import ClipboardEntry, ClipboardStorage

import platform

from typing import Optional
from fastapi import HTTPException
import os

import security_services

class FileRequest(BaseModel):
    path: str

    def set_path(self, path: str):
        self.path = path
        return self


class HandshakeRequest(BaseModel):
    device_id: str
    device_name: str
    platform: str
    protocol_version: int
    supports_text: bool
    supports_files: bool
    supports_encryption: bool


class HandshakeResponse(BaseModel):
    accepted: bool
    reason: str | None = None
    device_id: str
    device_name: str
    platform: str
    protocol_version: int
    supports_text: bool
    supports_files: bool
    supports_encryption: bool

CHUNK_SIZE = 1024 * 1024  # 1 MB

class EncryptedPayload(BaseModel):
    encrypted_jwt: str


def _try_decrypt_handshake_body(request: Request, raw_body: bytes) -> HandshakeRequest:
    """
    Accept either:
      - plain JSON matching HandshakeRequest
      - {"encrypted_jwt": "<JWE>"} wrapper, which is decrypted into HandshakeRequest

    Decryption only happens if the server has a configured private key.
    """
    try:
        # First, try plain JSON
        return HandshakeRequest.model_validate_json(raw_body)
    except Exception:
        pass

    try:
        encrypted_payload = EncryptedPayload.model_validate_json(raw_body)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid handshake payload") from e

    private_key = getattr(request.app.state, "private_key_pem", None)
    private_key_password = getattr(request.app.state, "private_key_password", None)

    if private_key is None:
        raise HTTPException(status_code=400, detail="Encrypted handshake not supported on this node")

    try:
        decrypted_dict = security_services.decrypt(
            private_key=private_key,
            encrypted_jwt=encrypted_payload.encrypted_jwt,
            password=private_key_password,
        )
        return HandshakeRequest.model_validate(decrypted_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to decrypt handshake payload") from e


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to an external address (doesn't need to be reachable)
        s.connect(('8.8.8.8', 80))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1' # Fallback to loopback if no network connection
    finally:
        s.close()
    return IP


def get_storage(request: Request) -> ClipboardStorage:
    return request.app.state.clipboard_storage


def get_paste_queue(request: Request) -> Queue:
    return request.app.state.paste_queue


def build_rest_router():
    rest_router = APIRouter(prefix="/api", tags=["api"])

    @rest_router.post("/handshake", response_model=HandshakeResponse)
    async def handshake(request: Request):
        print(request)
        raw_body = await request.body()
        req = _try_decrypt_handshake_body(request, raw_body)

        local_id = request.app.state.local_id
        local_name = request.app.state.device_name
        local_platform = platform.system()

        remote_ip = request.client.host
        if remote_ip not in request.app.state.peer_list:
            request.app.state.peer_list.append(remote_ip)
            print(f"[handshake] added peer {remote_ip} to peer_list")

        if req.device_id == local_id:
            return HandshakeResponse(
                accepted=False,
                reason="self",
                device_id=local_id,
                device_name=local_name,
                platform=local_platform,
                protocol_version=1,
                supports_text=True,
                supports_files=True,
                supports_encryption=False,
            )

        if req.protocol_version != 1:
            return HandshakeResponse(
                accepted=False,
                reason="protocol_mismatch",
                device_id=local_id,
                device_name=local_name,
                platform=local_platform,
                protocol_version=1,
                supports_text=True,
                supports_files=True,
                supports_encryption=False,
            )

        return HandshakeResponse(
            accepted=True,
            reason=None,
            device_id=local_id,
            device_name=local_name,
            platform=local_platform,
            protocol_version=1,
            supports_text=True,
            supports_files=True,
            supports_encryption=request.app.state.private_key_pem is not None,
        )


    @rest_router.get("/peers")
    async def get_peers(
            request: Request,
    ):
        return request.app.state.peer_list


    @rest_router.post("/clipboard_entry")
    async def post_clipboard_entry(
            entry: ClipboardEntry,
            request: Request,
            cs: ClipboardStorage = Depends(get_storage),
            pq: Queue = Depends(get_paste_queue),
    ):

        entry_origin = request.client.host
        entry.origin = entry_origin

        if cs.store_clipboard_entry(entry_origin, entry, pq):
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
            "Content-Disposition": f'attachment; filename="{quote(file_path.name)}"'
        }

        return StreamingResponse(
            iter_file(),
            headers=headers,
            media_type="application/octet-stream"
        )

    return rest_router


def broadcast_to_peers(entry: ClipboardEntry, peers: list = None, port: int = 8000) -> None:
    if peers is None:
        peers = [
            "localhost",  # Localhost is for testing purposes only
        ]

    payload = entry.model_dump(mode="json")  # datetime -> ISO string

    with httpx.Client(timeout=2) as client:
        for ip in peers:
            url = f"http://{ip}:{port}/api/clipboard_entry"
            try:
                r = client.post(url, json=payload)
                r.raise_for_status()
            except Exception as e:
                print(f"The type of list is {type(peers)}")
                print(f"[broadcast] failed to send to {ip}: {e}")


def get_files(paths: List[str], ip: str, port: int = 8000):
    import tempfile

    timeout = httpx.Timeout(connect=5, read=60, write=30, pool=5)
    url = f"http://{ip}:{port}/api/file"

    temp_dir = Path(tempfile.gettempdir()) / "LanClipboard"
    temp_dir.mkdir(parents=True, exist_ok=True)

    downloaded_paths = []

    with httpx.Client(timeout=timeout) as client:
        try:
            for str_path in paths:
                file_path = Path(str_path)
                file_name = file_path.name
                json_body = FileRequest(path=str_path)
                payload = json_body.model_dump(mode="json")

                with client.stream("POST", url, json=payload) as r:
                    r.raise_for_status()

                    temp_file = temp_dir / file_name
                    print(f"Saving {file_name} to {temp_file}")

                    with open(temp_file, "wb") as f:
                        chunk_num = 0
                        for chunk in r.iter_bytes(chunk_size=CHUNK_SIZE):
                            chunk_num += 1
                            print(f"Saving chunk # {chunk_num}")
                            f.write(chunk)

                    print(f"File {file_name} saved")
                    downloaded_paths.append(str(temp_file))

        except Exception as e:
            print(f"[file request] failed to receive from {ip}: {e}")

    return downloaded_paths