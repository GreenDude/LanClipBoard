"""Background worker: consume :class:`ClipboardEntry` objects from a queue and paste locally."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import logging
from queue import Empty, Queue

from abstract_clipboard import AbstractClipboard
import api_module
from clipboard_payloads import parse_file_list
from clipboard_storage import ClipboardEntry

logger = logging.getLogger(__name__)


def _entry_origin_is_local(queued_entry: ClipboardEntry, clipboard_storage) -> bool:
    """Return True when *queued_entry* originated on this device."""
    return queued_entry.origin in {"local", clipboard_storage.local_id}


def paste_queue_handler(
    stop_event,
    paste_queue: Queue,
    clipboard_implementation: AbstractClipboard,
    clipboard_storage,
    private_key: bytes,
    public_key: bytes,
    key_pass: bytes,
):
    """Apply queued clipboard entries (text or file lists) using *clipboard_implementation*.

    File entries fetch from the origin host via :func:`api_module.get_files`.
    """
    while not stop_event.is_set():
        try:
            queued_entry: ClipboardEntry = paste_queue.get(timeout=0.2)
        except Empty:
            continue

        if queued_entry is None:
            continue

        try:
            if queued_entry.type == "text":
                logger.info("[paste queue] processing text entry from %s", queued_entry.origin)
                clipboard_implementation.paste_clipboard_entry(queued_entry.entry)
                clipboard_storage.mark_programmatic_clipboard_write()

            elif queued_entry.type == "files":
                logger.info("[paste queue] processing file entry from %s", queued_entry.origin)
                if _entry_origin_is_local(queued_entry, clipboard_storage):
                    downloaded_paths = parse_file_list(queued_entry.entry)
                else:
                    downloaded_paths = api_module.get_files(
                        parse_file_list(queued_entry.entry),
                        queued_entry.origin,
                        public_key,
                        private_key,
                        key_pass,
                    )
                if downloaded_paths:
                    clipboard_implementation.paste_clipboard_entry(downloaded_paths)
                    clipboard_storage.mark_programmatic_clipboard_write()

            else:
                raise NotImplementedError(f"Unsupported clipboard entry type: {queued_entry.type}")
        except Exception:
            # Keep the queue handler alive even if one paste attempt fails.
            logger.exception("[paste queue] failed to process entry")
        finally:
            paste_queue.task_done()
