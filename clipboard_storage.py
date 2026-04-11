"""In-memory clipboard history keyed by peer, with optional Wayland paste-queue integration."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import os
import platform

from datetime import UTC, datetime

from pydantic import BaseModel

_supported_formats = ("text", "files")
_supported_platforms = ("Windows", "Darwin", "Linux")

_is_wayland = (
    platform.system() == "Linux"
    and os.environ.get("XDG_SESSION_TYPE") == "wayland"
)


class ClipboardEntry(BaseModel):
    """Wire format for a single clipboard payload exchanged between peers."""

    origin: str
    platform: str
    type: str
    entry: str
    timestamp: datetime


def _new_entry_is_valid(checked_entry: ClipboardEntry) -> bool:
    """Return True if *checked_entry* uses a known platform, allowed type, and non-empty *entry*."""
    if checked_entry.platform in _supported_platforms and checked_entry.type in _supported_formats and checked_entry.entry:
        return True
    else:
        return False


class ClipboardStorage:
    """Stores the latest :class:`ClipboardEntry` per remote address for the REST API and hotkey paste."""

    def __init__(self, local_id):
        """*local_id* is this device's stable id (e.g. ``\"Darwin@192.168.1.5\"``) used for Wayland routing."""
        self.storage_dict = dict()
        self.local_id = local_id

    def store_clipboard_entry(self, address: str, clip_entry: ClipboardEntry, paste_queue=None) -> bool:
        """Validate and store *clip_entry* under *address*; may enqueue for Wayland paste.

        On Wayland, entries whose *origin* differs from :attr:`local_id` are pushed to *paste_queue*
        so the user can paste remote content without a global keyboard hook.
        """
        # Check entry is valid
        if _new_entry_is_valid(clip_entry):
            # If client ip is registered create a new entry in the dictionary
            if address not in self.storage_dict:
                self.storage_dict[address] = [clip_entry]

            else:
                clip_entry_list = self.storage_dict[address]
                clip_entry_list.append(clip_entry)
                print(clip_entry_list)
                print(type(clip_entry_list))
                # remove entries with older timestamps
                latest_entry = max(clip_entry_list, key=lambda e: e.timestamp, default=None)
                print(f"latest_entry: {latest_entry}")
                clip_entry_list[:] = [latest_entry] if latest_entry else []

            if _is_wayland and clip_entry.origin != self.local_id:
                paste_queue.put(clip_entry)
            return True

        return False

    def get_all_clipboard_entries(self):
        """Return ``[(address, latest_entry), ...]`` or ``None`` when empty."""
        res = list()
        for entry in self.storage_dict:
            value = self.storage_dict[entry][len(self.storage_dict[entry]) - 1]
            res.append((entry, value))

        if len(res) > 0:
            print(f"Pulling Clipboard entries: {res}")
            return res
        else:
            return None

    def get_latest_clipboard_entry(self) -> ClipboardEntry | None:
        """Return the newest entry across all addresses by :attr:`ClipboardEntry.timestamp`."""
        timestamps = []
        for entry in self.storage_dict:
            clip_entry = self.storage_dict[entry][len(self.storage_dict[entry]) - 1]
            timestamps.append((entry, clip_entry.timestamp))

        if len(timestamps) > 0:
            latest_entry = max(timestamps, key=lambda e: e[1])[0]
            return self.storage_dict[latest_entry][len(self.storage_dict[latest_entry]) - 1]
        else:
            return None
