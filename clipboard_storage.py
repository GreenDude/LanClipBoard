from pydantic import BaseModel
from datetime import datetime, UTC

_supported_formats = ("text", "files")
_supported_platforms = ("Windows", "Darwin", "Linux")

class ClipboardEntry(BaseModel):
    platform: str
    type: str
    entry: str
    timestamp: datetime


def _new_entry_is_valid(checked_entry: ClipboardEntry) -> bool:
    if checked_entry.platform in _supported_platforms and checked_entry.type in _supported_formats and checked_entry.entry:
        return True
    else:
        return False


class ClipboardStorage:

    """
        storage dict contains client IP and stores current and new clipboard entries as lists.
        As soon as the entry the old entries are cleared based on the filter

    """
    def __init__(self):
        self.storage_dict = dict()

    def store_clipboard_entry(self, address: str, clip_entry: ClipboardEntry) -> bool:
        # Check entry is valid
        if _new_entry_is_valid(clip_entry):
            #If client ip is registered create a new entry in the dictionary
            if address not in self.storage_dict:
                self.storage_dict[address] = [clip_entry]
                return True

            else:
                clip_entry_list = self.storage_dict[address]
                clip_entry_list.append(clip_entry)
                print (clip_entry_list)
                print (type(clip_entry_list))
                #remove entries with older timestamps
                latest_entry = max(clip_entry_list, key=lambda e: e.timestamp, default=None)
                print (f"latest_entry: {latest_entry}")
                clip_entry_list[:] = [latest_entry] if latest_entry else []
                return True

        return False

    def get_all_clipboard_entries(self):
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
        timestamps = []
        for entry in self.storage_dict:
            clip_entry = self.storage_dict[entry][len(self.storage_dict[entry]) - 1]
            timestamps.append((entry, clip_entry.timestamp))

        if len(timestamps) > 0:
            latest_entry = max(timestamps, key=lambda e: e[1])[0]
            return self.storage_dict[latest_entry][len(self.storage_dict[latest_entry]) - 1]
        else:
            return None
