from contextlib import asynccontextmanager
from queue import Queue
from threading import Event, Thread
from fastapi import FastAPI

from clipboard_factory import get_clipboard
from api_module import build_rest_router
from clipboard_listener import monitor_clipboard
from clipboard_storage import ClipboardStorage
from keyboard_listener import monitor_keyboard
from paste_queue_handler import paste_queue_handler


@asynccontextmanager
async def async_clipboard_lifespan(app: FastAPI):
    # --- init state ---
    app.state.clipboard_storage = ClipboardStorage()
    app.state.clipboard = get_clipboard()

    local_id = "local"
    app.state.local_id = local_id

    # Queue recording items to paste from clipboard storage
    app.state.paste_queue = Queue()

    stop_event = Event()
    app.state.stop_event = stop_event

    # --- start background threads ---
    clipboard_thread = Thread(
        target=monitor_clipboard,
        args=(app.state.clipboard, app.state.clipboard_storage, local_id, stop_event),
        daemon=True,
        name="clipboard_thread",
    )

    keyboard_thread = Thread(
        target=monitor_keyboard,
        args=(stop_event, app.state.paste_queue, app.state.clipboard_storage,),          # <-- NOTE the comma is required
        daemon=True,
        name="keyboard_thread",
    )

    queue_handler_thread = Thread(
        target=paste_queue_handler,
        args=(stop_event, app.state.paste_queue, app.state.clipboard,),
        daemon=True,
        name="queue_handler_thread",
    )

    clipboard_thread.start()
    keyboard_thread.start()
    queue_handler_thread.start()

    app.state.clipboard_thread = clipboard_thread
    app.state.keyboard_thread = keyboard_thread
    app.state.queue_handler_thread = queue_handler_thread

    # --- app runs here ---
    try:
        yield
    finally:
        # --- shutdown ---
        stop_event.set()

        keyboard_thread.join(timeout=2)
        clipboard_thread.join(timeout=2)
        queue_handler_thread.join(timeout=2)


app = FastAPI(lifespan=async_clipboard_lifespan)
app.include_router(build_rest_router())