import ast
from queue import Queue, Empty
from cryptography.hazmat.primitives.asymmetric import rsa

from abstract_clipboard import AbstractClipboard
from clipboard_storage import ClipboardEntry
import api_module


def paste_queue_handler(stop_event,
                        paste_queue: Queue,
                        clipboard_implementation: AbstractClipboard,
                        private_key: rsa.RSAPrivateKey,
                        public_key: rsa.RSAPublicKey):
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
                ip_str = queued_entry.origin if queued_entry.origin != "local" else "localhost"
                downloaded_paths = api_module.get_files(
                    [p for p in ast.literal_eval(queued_entry.entry)],
                    ip_str,
                    public_key,
                    private_key
                )
                if downloaded_paths:
                    clipboard_implementation.paste_clipboard_entry(downloaded_paths)

            else:
                print("The entry type is not supported")
                raise NotImplementedError(f"Unsupported clipboard entry type: {queued_entry.type}")
        finally:
            paste_queue.task_done()