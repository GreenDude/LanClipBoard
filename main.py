"""FastAPI entrypoint: wires config, discovery, clipboard threads, and REST API."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
from contextlib import asynccontextmanager
import os
import shutil
from pathlib import Path
import platform
import socket
from queue import Queue
from threading import Event, Thread

from fastapi import FastAPI

from config.config_loader import load_config
from mdns_discovery import LanClipboardDiscovery
from clipboard_factory import get_clipboard
from api_module import build_rest_router, get_local_ip
from clipboard_listener import monitor_clipboard
from clipboard_storage import ClipboardStorage
from keyboard_listener import monitor_keyboard
from paste_queue_handler import paste_queue_handler

import tempfile
import security_services


def load_private_key_from_config(config):
    """Load PEM keys from the configured archive, or return three ``None`` values if disabled or on error.

    Extracts into a temporary directory, reads key material into memory, then deletes the directory.
    """
    none_key = None, None, None

    if not config.security.enabled:
        return none_key

    archive_path = config.security.key_archive
    password = config.security.key_password

    if not archive_path:
        return none_key

    archive_file = Path(archive_path)
    if not archive_file.exists():
        print(f"[security] key archive not found: {archive_file}")
        return none_key

    temp_dir: Path | None = None
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="lanclipboard_keys_"))
        extracted_files = security_services.unpack_keys(
            archive_path=archive_file,
            destination_dir=temp_dir,
            archive_password=password.encode("utf-8") if password else None,
        )

        private_key_file = next(
            (p for p in extracted_files if p.name.endswith("_private.pem") or p.name == "private_key.pem"),
            None,
        )

        public_key_file = next(
            (p for p in extracted_files if p.name.endswith("_public.pem") or p.name == "public_key.pem"),
            None,
        )

        if private_key_file is None:
            print("[security] private key not found in archive")
            return None, None, None

        if public_key_file is None:
            print("[security] public key not found in archive")
            return None, None, None

        private_key_pem = private_key_file.read_bytes()
        public_key_pem = public_key_file.read_bytes()
        pwd = password.encode("utf-8") if password else None

        return private_key_pem, public_key_pem, pwd

    except Exception as e:
        print(f"[security] failed to load key archive: {e}")
        return None, None, None
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)



def build_hotkey_set(keys: list[str]) -> set[str]:
    """Normalize configured hotkey tokens into a set for combo matching."""
    return set(keys)



@asynccontextmanager
async def async_clipboard_lifespan(app: FastAPI):
    """Start background threads, discovery, and shared app state; tear down on shutdown."""
    app.state.config = load_config()

    port = app.state.config.network.port
    device_name = (
        socket.gethostname() if app.state.config.device.name == "auto"
        else app.state.config.device.name
    )

    app.state.local_ip = get_local_ip()
    app.state.local_id = platform.system() + "@" + app.state.local_ip
    app.state.peer_list = []

    app.state.clipboard_storage = ClipboardStorage(app.state.local_id)
    app.state.clipboard = get_clipboard()

    app.state.device_name = device_name
    app.state.paste_hotkey = build_hotkey_set(app.state.config.hotkeys.paste)

    private_key_pem, public_key_pem, private_key_password = load_private_key_from_config(app.state.config)

    app.state.private_key_pem = private_key_pem
    app.state.public_key_pem = public_key_pem
    app.state.private_key_password = private_key_password

    if private_key_pem is not None:
        print("[security] private key loaded")
    else:
        print("[security] running without private key")

    app.state.paste_queue = Queue()

    stop_event = Event()
    app.state.stop_event = stop_event

    is_wayland = platform.system() == "Linux" and (os.environ.get("XDG_SESSION_TYPE") == "wayland")

    clipboard_thread = Thread(
        target=monitor_clipboard,
        args=(app.state.clipboard,
              app.state.clipboard_storage,
              app.state.local_id, stop_event,
              app.state.peer_list,
              app.state.config.clipboard.poll_interval_ms,
              app.state.public_key_pem,
              app.state.private_key_pem,
              app.state.private_key_password,
              ),
        daemon=True,
        name="clipboard_thread",
    )

    queue_handler_thread = Thread(
        target=paste_queue_handler,
        args=(
            stop_event,
            app.state.paste_queue,
            app.state.clipboard,
            app.state.private_key_pem,
            app.state.public_key_pem,
            app.state.private_key_password,
        ),
        daemon=True,
        name="queue_handler_thread",
    )

    print(f"[discovery] using local_ip={app.state.local_ip}")
    discovery_service = LanClipboardDiscovery(
        local_id=app.state.local_id,
        local_ip=app.state.local_ip,
        device_name=app.state.device_name,
        platform_name=platform.system(),
        port=port,
        protocol_version=1,
        peer_list=app.state.peer_list,
        peer_public_key_pem=app.state.public_key_pem
    )

    if app.state.config.network.discovery:
        await discovery_service.start()
    app.state.discovery_service = discovery_service

    bootstrap_peers = app.state.config.network.bootstrap_peers or []
    if bootstrap_peers:
        await discovery_service.bootstrap_handshake(bootstrap_peers)
    else:
        print("[discovery] no bootstrap peers configured, relying on service discovery only")

    clipboard_thread.start()
    queue_handler_thread.start()

    app.state.clipboard_thread = clipboard_thread
    app.state.queue_handler_thread = queue_handler_thread

    keyboard_thread = None

    if not is_wayland:
        keyboard_thread = Thread(
            target=monitor_keyboard,
            args=(
                stop_event,
                app.state.paste_queue,
                app.state.clipboard_storage,
                app.state.paste_hotkey,
            ),
            daemon=True,
            name="keyboard_thread",
        )
        keyboard_thread.start()
        app.state.keyboard_thread = keyboard_thread
    else:
        print("Wayland detected: keyboard listener disabled")

    try:
        yield
    finally:
        await discovery_service.stop()
        stop_event.set()

        if keyboard_thread is not None:
            keyboard_thread.join(timeout=2)

        clipboard_thread.join(timeout=2)
        queue_handler_thread.join(timeout=2)

app = FastAPI(lifespan=async_clipboard_lifespan)
app.include_router(build_rest_router())