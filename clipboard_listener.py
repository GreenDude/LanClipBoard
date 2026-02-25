import platform
import time
from datetime import datetime, UTC
from clipboard_storage import ClipboardEntry, ClipboardStorage
from abstract_clipboard import AbstractClipboard  # your ABC

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
                        platform=platform.system(),      # e.g. "Linux"/"Darwin"/"Windows"
                        type=clip_type,         # "text"/"files"
                        entry=clip_value,
                        timestamp=datetime.now(UTC),
                    )
                    # store under a dedicated key for "local machine"
                    storage.store_clipboard_entry(local_id, entry)

        except Exception:
            # Keep the thread alive; optionally log
            pass

        time.sleep(poll_interval)