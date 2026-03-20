import platform
import time
import traceback
from datetime import datetime, UTC

from api_module import broadcast_to_peers
from clipboard_storage import ClipboardEntry, ClipboardStorage
from abstract_clipboard import AbstractClipboard  # your ABC

def monitor_clipboard(
    clipboard: AbstractClipboard,
    storage: ClipboardStorage,
    local_id: str,
    stop_event,
    poll_interval: float = 0.25,
) -> None:
    last_fingerprint: tuple[str, str] | None = None  # (type, entry)

    while not stop_event.is_set():
        try:
            clip_type, clip_value = clipboard.get_clipboard_entry()

            if clip_value:
                fingerprint = (clip_type, clip_value)
                if fingerprint != last_fingerprint:
                    last_fingerprint = fingerprint

                    entry = ClipboardEntry(
                        origin=local_id,
                        platform=platform.system(),
                        type=clip_type,
                        entry=clip_value,
                        timestamp=datetime.now(UTC),
                    )
                    storage.store_clipboard_entry(local_id, entry)
                    broadcast_to_peers(entry)

        except Exception:
            print(f"Well that was unexpected {last_fingerprint}")
            print(traceback.format_exc())
            # Keep the thread alive; optionally log
            pass

        time.sleep(poll_interval)