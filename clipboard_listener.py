"""Poll the local clipboard and broadcast changes to known peers."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import logging
import platform
import time
from datetime import UTC, datetime
from threading import Event

from abstract_clipboard import AbstractClipboard
from api_module import broadcast_to_peers
from clipboard_payloads import parse_file_list
from clipboard_storage import ClipboardEntry, ClipboardStorage
from peer_registry import PeerRegistry
from shared_file_registry import SharedFileRegistry

logger = logging.getLogger(__name__)


def monitor_clipboard(
        clipboard: AbstractClipboard,
        clipboard_storage: ClipboardStorage,
        local_id: str,
        stop_event: Event,
        peer_registry: PeerRegistry,
        poll_interval: int,
        public_key_pem,
        private_key_pem,
        password,
        shared_file_registry: SharedFileRegistry,
        ) -> None:
    """Poll *clipboard* until *stop_event*; dedupe by (type, value) and broadcast to *peer_list*."""

    last_fingerprint: tuple[str, str] | None = None  # (type, entry)

    while not stop_event.is_set():
        try:
            clip_type, clip_value = clipboard.get_clipboard_entry()

            if clip_value:
                fingerprint = (clip_type, clip_value)
                if fingerprint != last_fingerprint:
                    if clipboard_storage.consume_programmatic_clipboard_write():
                        last_fingerprint = fingerprint
                        continue
                    last_fingerprint = fingerprint

                    entry = ClipboardEntry(
                        origin=local_id,
                        platform=platform.system(),
                        type=clip_type,
                        entry=clip_value,
                        timestamp=datetime.now(UTC),
                    )
                    if clip_type == "files":
                        shared_file_registry.register_paths(parse_file_list(clip_value))
                    clipboard_storage.store_clipboard_entry(local_id, entry)
                    broadcast_to_peers(entry=entry,
                                       peers=peer_registry,
                                       public_key_pem = public_key_pem,
                                       private_key_pem = private_key_pem,
                                       private_key_password  = password)

        except Exception:
            logger.exception("[clipboard] unexpected monitor error fingerprint=%s", last_fingerprint)

        sleep_time = poll_interval / 1000
        time.sleep(sleep_time)
