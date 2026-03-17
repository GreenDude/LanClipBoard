import platform
import time
import traceback
from datetime import datetime, UTC

from api_module import broadcast_to_peers
from clipboard_storage import ClipboardEntry, ClipboardStorage
from abstract_clipboard import AbstractClipboard  # your ABC

PEER_LIST = [
    # "localhost",  # Localhost is for testing purposes only
    # "192.168.100.17", # Win
    # "192.168.100.61", # Mac
    "192.168.100.54", # Lenovo Fedora

]

def monitor_clipboard(
    clipboard: AbstractClipboard,
    storage: ClipboardStorage,
    local_id: str,
    stop_event,
    poll_interval: float = 0.25,
) -> None:
    """
    Runs in a thread. Polls clipboard and stores new entries when changed.
    """
    last_fingerprint: tuple[str, str] | None = None  # (type, entry)

    while not stop_event.is_set():
        try:
            # Expect your clipboard implementation returns something like:
            # ("text", "hello world") or ("files", "/path/a;/path/b")
            clip_type, clip_value = clipboard.get_clipboard_entry()

            if clip_value:
                fingerprint = (clip_type, clip_value)
                if fingerprint != last_fingerprint:
                    last_fingerprint = fingerprint

                    entry = ClipboardEntry(
                        origin=local_id,
                        platform=platform.system(),      # e.g. "Linux"/"Darwin"/"Windows"
                        type=clip_type,         # "text"/"files"
                        entry=clip_value,
                        timestamp=datetime.now(UTC),
                    )
                    # store under a dedicated key for "local machine"
                    storage.store_clipboard_entry(local_id, entry)
                    broadcast_to_peers(entry, PEER_LIST)

        except Exception:
            print(f"Well that was unexpected {last_fingerprint}")
            print(traceback.format_exc())
            # Keep the thread alive; optionally log
            pass

        time.sleep(poll_interval)