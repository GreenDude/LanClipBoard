"""Poll the local clipboard and broadcast changes to known peers."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import platform
import time
import traceback
from datetime import UTC, datetime
from threading import Event

from abstract_clipboard import AbstractClipboard
from api_module import broadcast_to_peers
from clipboard_storage import ClipboardEntry, ClipboardStorage


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
    """Poll *clipboard* until *stop_event*; dedupe by (type, value) and broadcast to *peer_list*."""

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