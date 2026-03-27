import asyncio
from contextlib import asynccontextmanager
from queue import Queue
from threading import Event, Thread

import yaml
from fastapi import FastAPI
import os
import json
from pathlib import Path
import platform
import socket

from config.config_loader import AppConfig, load_config
from mdns_discovery import LanClipboardDiscovery
from clipboard_factory import get_clipboard
from api_module import build_rest_router, get_local_ip
from clipboard_listener import monitor_clipboard
from clipboard_storage import ClipboardStorage
from keyboard_listener import monitor_keyboard
from paste_queue_handler import paste_queue_handler


def load_config(path: str = "config/config.yaml") -> AppConfig:
    config_path = Path(path)

    if not config_path.exists():
        raise RuntimeError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return AppConfig(**raw)


def load_private_key_from_config(config):
    if not config.security.enabled:
        return None, None

    archive_path = config.security.key_archive
    password = config.security.key_password

    if not archive_path:
        return None, None

    archive_file = Path(archive_path)
    if not archive_file.exists():
        print(f"[security] key archive not found: {archive_file}")
        return None, None

    try:
        with open(archive_file, "r", encoding="utf-8") as f:
            archive_data = json.load(f)

        private_key_pem = archive_data.get("private_key_pem")
        if not private_key_pem:
            print("[security] private_key_pem missing from key archive")
            return None, None

        return private_key_pem.encode("utf-8"), (
            password.encode("utf-8") if password else None
        )

    except Exception as e:
        print(f"[security] failed to load key archive: {e}")
        return None, None

def build_hotkey_set(keys: list[str]) -> set[str]:
    return set(keys)



@asynccontextmanager
async def async_clipboard_lifespan(app: FastAPI):
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

    private_key_pem, private_key_password = load_private_key_from_config(app.state.config)
    app.state.private_key_pem = private_key_pem
    app.state.private_key_password = private_key_password

    if private_key_pem is not None:
        print("[security] private key loaded")
    else:
        print("[security] running without private key")

    app.state.paste_queue = Queue()
    app.state.is_pasting = False

    stop_event = Event()
    app.state.stop_event = stop_event

    is_wayland = platform.system() == "Linux" and (os.environ.get("XDG_SESSION_TYPE") == "wayland")

    clipboard_thread = Thread(
        target=monitor_clipboard,
        args=(app.state.clipboard,
              app.state.clipboard_storage,
              app.state.local_id, stop_event,
              app.state.peer_list,
              app.state.config,
              ),
        daemon=True,
        name="clipboard_thread",
    )

    queue_handler_thread = Thread(
        target=paste_queue_handler,
        args=(stop_event, app.state.paste_queue, app.state.clipboard,),
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
    )
    print (f"app.state.config.network.discovery == {app.state.config.network.discovery}")
    if app.state.config.network.discovery:
        await discovery_service.start()
    app.state.discovery_service = discovery_service

    if app.state.config.network.bootstrap_peers:
        await discovery_service.bootstrap_handshake(app.state.config.network.bootstrap_peers)

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
                app.state.is_pasting,
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