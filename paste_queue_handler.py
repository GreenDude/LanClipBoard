from queue import Queue, Empty

from abstract_clipboard import AbstractClipboard
from clipboard_storage import ClipboardEntry


def paste_queue_handler(stop_event, paste_queue: Queue, clipboard_implementation: AbstractClipboard):
    while not stop_event.is_set():
        try:
            queued_entry: ClipboardEntry = paste_queue.get(timeout=0.2)
            print("Entered paste thread")
        except Empty:
            continue

        if queued_entry is None:
            continue

        try:
            if queued_entry.type == "text":
                print("If the entry type is text")
                clipboard_implementation.paste_clipboard_entry(queued_entry.entry)
            elif queued_entry.type == "files":
                print("If the entry type is files")
                # API call / file fetch
                pass
            else:
                print("The entry type is not supported")
                raise NotImplementedError(f"Unsupported clipboard entry type: {queued_entry.type}")
        finally:
            paste_queue.task_done()