import asyncio
from contextlib import asynccontextmanager
from queue import Queue
from threading import Event, Thread
from fastapi import FastAPI
import os
import platform
import socket

from mdns_discovery import LanClipboardDiscovery
from clipboard_factory import get_clipboard
from api_module import build_rest_router
from clipboard_listener import monitor_clipboard
from clipboard_storage import ClipboardStorage
from keyboard_listener import monitor_keyboard
from paste_queue_handler import paste_queue_handler

def get_lan_ip():
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


@asynccontextmanager
async def async_clipboard_lifespan(app: FastAPI):
    app.state.local_id = platform.system() + "@" + get_lan_ip()

    app.state.clipboard_storage = ClipboardStorage(app.state.local_id)
    app.state.clipboard = get_clipboard()


    device_name = socket.gethostname()
    app.state.device_name = device_name

    # Queue recording items to paste from clipboard storage
    app.state.paste_queue = Queue()
    app.state.is_pasting = False

    stop_event = Event()
    app.state.stop_event = stop_event

    is_wayland = platform.system() == "Linux" and (os.environ.get("XDG_SESSION_TYPE") == "wayland")

    clipboard_thread = Thread(
        target=monitor_clipboard,
        args=(app.state.clipboard, app.state.clipboard_storage, app.state.local_id, stop_event,),
        daemon=True,
        name="clipboard_thread",
    )

    queue_handler_thread = Thread(
        target=paste_queue_handler,
        args=(stop_event, app.state.paste_queue, app.state.clipboard,),
        daemon=True,
        name="queue_handler_thread",
    )

    discovery_service = LanClipboardDiscovery(
        local_id=app.state.local_id,
        device_name=app.state.device_name,
        platform_name=platform.system(),
        port=8000,
        protocol_version=1,
    )

    await asyncio.to_thread(discovery_service.start)
    app.state.discovery_service = discovery_service

    clipboard_thread.start()
    queue_handler_thread.start()

    app.state.clipboard_thread = clipboard_thread
    app.state.queue_handler_thread = queue_handler_thread

    keyboard_thread = None

    if not is_wayland:
        keyboard_thread = Thread(
            target=monitor_keyboard,
            args=(stop_event, app.state.paste_queue, app.state.clipboard_storage, app.state.is_pasting),
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
        await asyncio.to_thread(discovery_service.stop())
        stop_event.set()
        if keyboard_thread is not None:
            keyboard_thread.join(timeout=2)

        clipboard_thread.join(timeout=2)
        queue_handler_thread.join(timeout=2)


app = FastAPI(lifespan=async_clipboard_lifespan)
app.include_router(build_rest_router())