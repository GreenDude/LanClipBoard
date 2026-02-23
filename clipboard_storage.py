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

def test1():
    first_test_entry = ClipboardEntry(
        platform="Windows",
        type="text",
        entry="text",
        timestamp=datetime.now(UTC),
    )

    json_entry = first_test_entry.model_dump_json()
    print(f"Clipboard entry: {json_entry}")

    cs = ClipboardStorage()
    print(cs.store_clipboard_entry("IP1", first_test_entry))
    print (cs.storage_dict.values())

def test2():
    first_test_entry = ClipboardEntry(
        platform="Windows",
        type="text",
        entry="text1",
        timestamp=datetime.now(UTC),
    )
    from time import sleep
    sleep(2)
    second_test_entry = ClipboardEntry(
        platform="Windows",
        type="text",
        entry="text2",
        timestamp=datetime.now(UTC),
    )

    cs = ClipboardStorage()
    print(cs.store_clipboard_entry("IP1", first_test_entry))
    print(cs.store_clipboard_entry("IP1", second_test_entry))
    to_print = cs.storage_dict.get("IP1")
    for value in to_print:
        json_value = value.model_dump_json()
        print(f"Test 2 Clipboard entry: {json_value}")

def test3():
    first_test_entry = ClipboardEntry(
        platform="Windows",
        type="test",
        entry="text",
        timestamp=datetime.now(UTC),
    )

    json_entry = first_test_entry.model_dump_json()
    print(f"Clipboard entry: {json_entry}")

    cs = ClipboardStorage()
    print(cs.store_clipboard_entry("IP1", first_test_entry))
    print(cs.storage_dict.values())


if __name__ == "__main__":
    test1()
    print("><#><" * 20)
    test2()
    print("><#><" * 20)
    test3()
    print("><#><" * 20)