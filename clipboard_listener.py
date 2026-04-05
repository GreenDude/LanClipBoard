import platform
from threading import Event
import time
import traceback
from datetime import datetime, UTC

from api_module import broadcast_to_peers
from clipboard_storage import ClipboardEntry, ClipboardStorage
from abstract_clipboard import AbstractClipboard  # your ABC
from config.config_loader import AppConfig


def monitor_clipboard(
        clipboard: AbstractClipboard,
        clipboard_storage: ClipboardStorage,
        local_id: str,
        stop_event: Event,
        peer_list: list,
        poll_interval: int,
        public_key_pem,
        private_key_pem,
        password,
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
                    clipboard_storage.store_clipboard_entry(local_id, entry)
                    print(f"Peer List type: {type(peer_list)} contain {peer_list}")
                    broadcast_to_peers(entry=entry,
                                       peers=peer_list,
                                       public_key_pem = public_key_pem,
                                       private_key_pem = private_key_pem,
                                       private_key_password  = password)

        except Exception:
            print(f"Well that was unexpected {last_fingerprint}")
            print(traceback.format_exc())
            # Keep the thread alive; optionally log
            pass

        sleep_time = poll_interval / 1000
        time.sleep(sleep_time)