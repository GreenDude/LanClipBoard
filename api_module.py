"""HTTP API: clipboard sync, peer handshake, and optional JWE-wrapped payloads."""

import json
import logging
import platform
import socket
from pathlib import Path
from queue import Queue
from typing import Any, List, Type
from urllib.parse import unquote

import aiofiles
import httpx
from fastapi import APIRouter, HTTPException, Request, responses
from fastapi.params import Depends
from pydantic import BaseModel, field_validator
from starlette.responses import StreamingResponse

import security_services
from clipboard_storage import ClipboardEntry, ClipboardStorage

logger = logging.getLogger(__name__)


class FileRequest(BaseModel):
    """Request body for ``POST /api/file`` (path to read and stream back)."""

    path: str

    @field_validator("path")
    @classmethod
    def reject_path_traversal(cls, v: str) -> str:
        if ".." in Path(v).parts:
            raise ValueError("path must not contain '..' components")
        return v

    def set_path(self, path: str):
        """Fluent helper used by callers building a request object."""
        self.path = path
        return self


class HandshakeRequest(BaseModel):
    """Client hello during peer discovery or bootstrap."""

    device_id: str
    device_name: str
    platform: str
    protocol_version: int
    supports_text: bool
    supports_files: bool
    supports_encryption: bool


class HandshakeResponse(BaseModel):
    """Server response including local capability flags and optional *reason* when rejected."""

    accepted: bool
    reason: str | None = None
    device_id: str
    device_name: str
    platform: str
    protocol_version: int
    supports_text: bool
    supports_files: bool
    supports_encryption: bool


class EncryptedPayload(BaseModel):
    """Wrapper JSON for compact JWE strings on the wire."""

    encrypted_jwt: str


CHUNK_SIZE = 1024 * 1024  #: 1 MiB; used for file streaming and download chunks.


def _attachment_content_disposition(filename: str) -> str:
    """Return a ``Content-Disposition`` value that preserves spaces in *filename*.

    Using :func:`urllib.parse.quote` here encodes spaces as ``%20``, which clients then save as
    literal characters in the basename; we only escape ``\\`` and ``"`` for the quoted-string form.
    """
    escaped = filename.replace("\\", "\\\\").replace('"', '\\"')
    return f'attachment; filename="{escaped}"'


def _try_decrypt_body(request: Request, raw_body: bytes, model_cls: Type[BaseModel]) -> str:
    """
    Returns a JSON string.

    Behavior:
      - If security is enabled on this node, only encrypted payloads are accepted.
      - If security is disabled, plain JSON is accepted.
      - Encrypted payloads are decrypted into model_cls-compatible JSON.
    """
    private_key = getattr(request.app.state, "private_key_pem", None)
    private_key_password = getattr(request.app.state, "private_key_password", None)

    security_enabled = private_key is not None

    if security_enabled:
        try:
            encrypted_payload = EncryptedPayload.model_validate_json(raw_body)
        except Exception:
            logger.warning(
                "Rejected body for encrypted endpoint: not valid EncryptedPayload (len=%s)",
                len(raw_body),
            )
            raise HTTPException(status_code=401, detail="Received unencrypted payload")

        try:
            decrypted_dict = security_services.decrypt_text(
                private_key=private_key,
                encrypted_jwt=encrypted_payload.encrypted_jwt,
                password=private_key_password,
            )
            model_cls.model_validate(decrypted_dict)
            return json.dumps(decrypted_dict)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Failed to decrypt payload") from e

    try:
        model_cls.model_validate_json(raw_body)
        return raw_body.decode("utf-8")
    except Exception:
        pass

    try:
        encrypted_payload = EncryptedPayload.model_validate_json(raw_body)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid request payload") from e

    if private_key is None:
        raise HTTPException(status_code=400, detail="Encrypted payload not supported on this node")

    try:
        decrypted_dict = security_services.decrypt_text(
            private_key=private_key,
            encrypted_jwt=encrypted_payload.encrypted_jwt,
            password=private_key_password,
        )
        model_cls.model_validate(decrypted_dict)
        return json.dumps(decrypted_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to decrypt payload") from e


def _parse_handshake_body(request: Request, raw_body: bytes) -> str:
    """Return JSON text for a :class:`HandshakeRequest`.

    Plaintext handshake JSON is always accepted so mDNS/bootstrap can complete even when
    this node loads a private key (clipboard/file traffic may still require JWE).

    If plaintext validation fails, falls back to :func:`_try_decrypt_body` so encrypted
    handshakes remain supported when the client has the correct public key material.
    """
    try:
        HandshakeRequest.model_validate_json(raw_body)
        return raw_body.decode("utf-8")
    except Exception:
        pass
    return _try_decrypt_body(request, raw_body, HandshakeRequest)


def _try_encrypt_body(payload: Any, peer_public_key_pem: bytes | None) -> dict:
    """
    Returns a JSON-serializable request body.

    If peer_public_key_pem is provided:
        {"encrypted_jwt": "<jwe>"}

    Otherwise:
        plain JSON dict
    """
    if isinstance(payload, BaseModel):
        payload_dict = payload.model_dump(mode="json")
    elif isinstance(payload, dict):
        payload_dict = payload
    else:
        raise TypeError(f"Unsupported payload type: {type(payload)}")

    if peer_public_key_pem is None:
        return payload_dict

    encrypted_jwt = security_services.encrypt_text(peer_public_key_pem, payload_dict)
    return {"encrypted_jwt": encrypted_jwt}


def get_local_ip():
    """Best-effort primary IPv4 for outbound traffic; falls back to loopback."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip_addr = s.getsockname()[0]
    except Exception:
        ip_addr = "127.0.0.1"
    finally:
        s.close()
    return ip_addr


def get_storage(request: Request) -> ClipboardStorage:
    """FastAPI dependency: shared :class:`ClipboardStorage` instance."""
    return request.app.state.clipboard_storage


def get_paste_queue(request: Request) -> Queue:
    """FastAPI dependency: queue consumed by the paste worker thread."""
    return request.app.state.paste_queue


def get_public_key(request: Request) -> bytes | None:
    """PEM-encoded local public key, or ``None`` when security is off."""
    return request.app.state.public_key_pem


def get_private_key(request: Request) -> bytes | None:
    """PEM-encoded local private key, or ``None`` when security is off."""
    return request.app.state.private_key_pem


def get_known_peers(request: Request) -> list[str]:
    """IPs that have completed handshake (or bootstrap); used as a coarse ACL."""
    return request.app.state.peer_list


def build_rest_router():
    """Construct the versioned REST API mounted under ``/api``."""
    rest_router = APIRouter(prefix="/api", tags=["api"])

    @rest_router.get("/")
    async def get_root():
        """Redirect browsers to OpenAPI docs."""
        return responses.RedirectResponse("/docs")

    @rest_router.post("/handshake", response_model=HandshakeResponse)
    async def handshake(request: Request):
        """Accept a peer handshake; may register the caller's IP in :attr:`app.state.peer_list`."""
        raw_body = await request.body()
        req_json = _parse_handshake_body(request, raw_body)
        req = HandshakeRequest.model_validate_json(req_json)

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
    async def get_peers(request: Request):
        """Return the in-memory list of peer IPs that have handshaked."""
        return request.app.state.peer_list

    @rest_router.post("/clipboard_entry")
    async def post_clipboard_entry(
        request: Request,
        cs: ClipboardStorage = Depends(get_storage),
        pq: Queue = Depends(get_paste_queue),
        known_peers: list[str] = Depends(get_known_peers),
    ):
        """Ingest a remote clipboard entry (JWE when security is enabled) and store it locally."""
        if request.client.host not in known_peers:
            raise HTTPException(status_code=403, detail="Peer is not authorized")

        raw_body = await request.body()
        entry_json = _try_decrypt_body(request, raw_body, ClipboardEntry)
        entry = ClipboardEntry.model_validate_json(entry_json)

        entry_origin = request.client.host
        entry.origin = entry_origin

        if cs.store_clipboard_entry(entry_origin, entry, pq):
            return {
                "host": request.client.host,
                "platform": entry.platform,
                "entry": entry.entry,
                "timestamp": entry.timestamp,
            }
        raise HTTPException(
            status_code=422,
            detail="Clipboard entry rejected (invalid type, empty payload, or unsupported platform).",
        )

    @rest_router.get("/clipboard_entries")
    async def get_clipboard_entries(cs: ClipboardStorage = Depends(get_storage)):
        """Return all latest entries per peer address."""
        entries = cs.get_all_clipboard_entries()
        return {"entries": entries or []}

    @rest_router.get("/clipboard_entries/latest")
    async def get_clipboard_entry(cs: ClipboardStorage = Depends(get_storage)):
        """Return the single newest stored entry, or JSON ``null``."""
        return cs.get_latest_clipboard_entry() if cs.get_latest_clipboard_entry() else None

    @rest_router.post("/file")
    async def get_file(
        request: Request,
        public_key_pem: bytes | None = Depends(get_public_key),
        known_peers: list[str] = Depends(get_known_peers),
    ):
        """Stream a file from a server-local path (optionally encrypted for the requester)."""

        if request.client.host not in known_peers:
            raise HTTPException(status_code=403, detail="Unauthorized peer")

        raw_body = await request.body()
        req_json = _try_decrypt_body(request, raw_body, FileRequest)
        file_request = FileRequest.model_validate_json(req_json)
        base_file_path = Path(file_request.path)

        if public_key_pem is None:
            file_path = base_file_path
        else:
            encrypted_file_path = security_services.encrypt_file(public_key_pem, base_file_path)
            if encrypted_file_path is not None:
                file_path = Path(encrypted_file_path)
            else:
                raise HTTPException(status_code=500, detail="Failed to encrypt file for transfer")

        async def iter_file():
            """Yield *file_path* in :data:`CHUNK_SIZE` blocks for streaming responses."""
            async with aiofiles.open(file_path, "rb") as f:
                while chunk := await f.read(CHUNK_SIZE):
                    yield chunk

        headers = {"Content-Disposition": _attachment_content_disposition(file_path.name)}

        return StreamingResponse(
            iter_file(),
            headers=headers,
            media_type="application/octet-stream",
        )

    return rest_router


def broadcast_to_peers(
    entry: ClipboardEntry,
    peers: list = None,
    public_key_pem: bytes | None = None,
    private_key_pem: bytes | None = None,
    private_key_password: bytes | None = None,
    port: int = 8000,

) -> None:
    """POST *entry* to each peer's ``/api/clipboard_entry`` (JWE when *public_key_pem* is set).

    The same PEM is used for every recipient; in typical deployments all peers share one key
    archive so encrypting with the local public key matches the peers' key material.
    """
    if peers is None:
        peers = ["localhost"]

    request_body = _try_encrypt_body(entry, public_key_pem)

    with httpx.Client(timeout=2) as client:
        for ip in peers:
            url = f"http://{ip}:{port}/api/clipboard_entry"
            try:
                r = client.post(url, json=request_body)
                r.raise_for_status()

                if private_key_pem is not None:
                    try:
                        response_json = r.json()
                        print(f"Received a response from {ip} with body \n\t{response_json}")
                        if "encrypted_jwt" in response_json:
                            decrypted_response = security_services.decrypt_text(
                                private_key=private_key_pem,
                                encrypted_jwt=response_json["encrypted_jwt"],
                                password=private_key_password,
                            )
                            print(f"[broadcast] decrypted response from {ip}: {decrypted_response}")
                    except Exception as e:
                        print(f"[broadcast] failed to decrypt response from {ip}: {e}")

            except Exception as e:
                print(f"[broadcast] failed to send to {ip}: {e}")


def get_files(
    paths: List[str],
    ip: str,
    public_key: bytes | None,
    private_key: bytes | None,
    key_pass: bytes | None,
    port: int = 8000,
):
    """Download files from *ip* via ``POST /api/file`` into a temp directory, decrypting ``*.enc`` when needed.

    Failures are logged; returns a list of local paths successfully retrieved (possibly partial).
    """
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

                if public_key is None:
                    payload = json_body.model_dump(mode="json")
                else:
                    payload = _try_encrypt_body(json_body.model_dump(mode="json"),
                                            public_key)
                print(f"Requesting \n\t{json_body}\n\n{payload}\n\n\n")
                with client.stream("POST", url, json=payload) as r:
                    r.raise_for_status()

                    downloaded_name = file_name
                    content_disposition = r.headers.get("Content-Disposition")
                    if content_disposition and "filename=" in content_disposition:
                        try:
                            downloaded_name = content_disposition.split("filename=")[1].strip().strip('"')
                            # Undo percent-encoding from older servers (e.g. %20 for spaces).
                            downloaded_name = unquote(downloaded_name)
                        except Exception:
                            downloaded_name = file_name

                    temp_file = temp_dir / downloaded_name
                    print(f"Saving {file_name} to {temp_file}")

                    with open(temp_file, "wb") as f:
                        chunk_num = 0
                        for chunk in r.iter_bytes(chunk_size=CHUNK_SIZE):
                            chunk_num += 1
                            print(f"Saving chunk # {chunk_num}")
                            f.write(chunk)

                    print(f"File {file_name} saved")
                    if temp_file.suffix == ".enc":
                        decrypted_file_path = security_services.decrypt_file(private_key, key_pass, str(temp_file))
                        temp_file.unlink(missing_ok=True)
                        if decrypted_file_path is not None:
                            downloaded_paths.append(decrypted_file_path)
                        else:
                            raise ValueError(f"Failed to decrypt downloaded file: {temp_file}")
                    else:
                        downloaded_paths.append(str(temp_file))
        except Exception as e:
            print(f"[file request] failed to receive from {ip}: {e}")

    return downloaded_paths