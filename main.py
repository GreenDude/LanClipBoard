import platform
from contextlib import asynccontextmanager
from threading import Event, Thread

from fastapi import FastAPI

from clipboard_factory import get_clipboard
from api_module import build_rest_router
from clipboard_listener import monitor_clipboard
from clipboard_storage import ClipboardStorage


@asynccontextmanager
async def async_clipboard_lifespan(app: FastAPI):
    app.state.clipboard_storage = ClipboardStorage()
    app.state.clipboard = get_clipboard()
    print(type(app.state.clipboard))

    local_id = "local"
    app.state.local_id = local_id

    stop_event = Event()
    app.state.stop_event = stop_event

    clipboard_thread = Thread(
        target=monitor_clipboard,
        args=(app.state.clipboard, app.state.clipboard_storage, local_id, stop_event),
        daemon=True,
    )

    clipboard_thread.start()
    app.state.clipboard_thread = clipboard_thread
    yield
    stop_event.set()
    clipboard_thread.join(timeout = 2)

app = FastAPI(lifespan=async_clipboard_lifespan)
app.include_router(build_rest_router())
