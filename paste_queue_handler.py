from queue import Queue

from abstract_clipboard import AbstractClipboard
from clipboard_storage import ClipboardStorage, ClipboardEntry


def paste_queue_handler(stop_event, paste_queue: Queue, clipboard_implementation: AbstractClipboard, clipboard_storage: ClipboardStorage):
    while not stop_event.is_set():
        if paste_queue.qsize() > 0:

            queued_entry: ClipboardEntry = paste_queue.get()
            if queued_entry is not None:
                if queued_entry.type == "text":
                    clipboard_implementation.paste_clipboard_entry(queued_entry.entry)
                elif queued_entry.type == "files":
                    #API Call
                    pass
                else:
                    raise NotImplementedError