"""In-memory clipboard history keyed by peer, with optional Wayland paste-queue integration."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import os
import platform
import time
from threading import RLock

from datetime import UTC, datetime

from pydantic import BaseModel
from clipboard_payloads import parse_file_list

_supported_formats = ("text", "files")
_supported_platforms = ("Windows", "Darwin", "Linux")

_is_wayland = (
    platform.system() == "Linux"
    and os.environ.get("XDG_SESSION_TYPE") == "wayland"
)
_MAX_ENTRY_LENGTH = 100_000


class ClipboardEntry(BaseModel):
    """Wire format for a single clipboard payload exchanged between peers."""

    origin: str
    platform: str
    type: str
    entry: str
    timestamp: datetime


def _new_entry_is_valid(checked_entry: ClipboardEntry) -> bool:
    """Return True if *checked_entry* uses a known platform, allowed type, and non-empty *entry*."""
    if checked_entry.platform not in _supported_platforms:
        return False
    if checked_entry.type not in _supported_formats:
        return False
    if not checked_entry.entry or len(checked_entry.entry) > _MAX_ENTRY_LENGTH:
        return False
    if checked_entry.type == "files":
        try:
            paths = parse_file_list(checked_entry.entry)
        except ValueError:
            return False
        return len(paths) > 0
    return True


class ClipboardStorage:
    """Stores the latest :class:`ClipboardEntry` per remote address for the REST API and hotkey paste."""

    def __init__(self, local_id):
        """*local_id* is this device's stable id (e.g. ``\"Darwin@192.168.1.5\"``) used for Wayland routing."""
        self.storage_dict = dict()
        self.local_id = local_id
        self._lock = RLock()
        self._suppress_next_local_change_until = 0.0

    def store_clipboard_entry(self, address: str, clip_entry: ClipboardEntry, paste_queue=None) -> bool:
        """Validate and store *clip_entry* under *address*; may enqueue for Wayland paste.

        On Wayland, entries whose *origin* differs from :attr:`local_id` are pushed to *paste_queue*
        so the user can paste remote content without a global keyboard hook.
        """
        # Check entry is valid
        if _new_entry_is_valid(clip_entry):
            with self._lock:
                current_entry = self.storage_dict.get(address)
                if current_entry is None or clip_entry.timestamp >= current_entry.timestamp:
                    self.storage_dict[address] = clip_entry

            if _is_wayland and clip_entry.origin != self.local_id:
                paste_queue.put(clip_entry)
            return True

        return False

    def get_all_clipboard_entries(self):
        """Return ``[(address, latest_entry), ...]`` or ``None`` when empty."""
        with self._lock:
            res = list(self.storage_dict.items())

        if len(res) > 0:
            return res
        else:
            return None

    def get_latest_clipboard_entry(self) -> ClipboardEntry | None:
        """Return the newest entry across all addresses by :attr:`ClipboardEntry.timestamp`."""
        with self._lock:
            if not self.storage_dict:
                return None
            return max(self.storage_dict.values(), key=lambda entry: entry.timestamp)

    def mark_programmatic_clipboard_write(self, ttl_seconds: float = 1.5) -> None:
        """Suppress the next clipboard poll result after LanClipboard updates the local clipboard itself."""
        with self._lock:
            self._suppress_next_local_change_until = time.monotonic() + ttl_seconds

    def consume_programmatic_clipboard_write(self) -> bool:
        """Return True once when a locally written clipboard update should not be rebroadcast."""
        with self._lock:
            if time.monotonic() <= self._suppress_next_local_change_until:
                self._suppress_next_local_change_until = 0.0
                return True
            return False
