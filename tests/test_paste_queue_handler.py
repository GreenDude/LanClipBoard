"""Tests for :mod:`paste_queue_handler`."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
from datetime import UTC, datetime
from queue import Queue
from threading import Event
from types import SimpleNamespace

import paste_queue_handler
from clipboard_payloads import serialize_file_list
from clipboard_storage import ClipboardEntry


def _make_file_entry(origin: str, paths: list[str]) -> ClipboardEntry:
    return ClipboardEntry(
        origin=origin,
        platform="Darwin",
        type="files",
        entry=serialize_file_list(paths),
        timestamp=datetime.now(UTC),
    )


def test_local_file_entry_skips_http_fetch(monkeypatch):
    q = Queue()
    q.put(_make_file_entry("Darwin@192.168.100.64", ["/tmp/a.txt", "/tmp/b.txt"]))

    stop_event = Event()
    pasted = []
    marks = []

    def paste_and_stop(paths):
        pasted.append(paths)
        stop_event.set()

    clipboard = SimpleNamespace(paste_clipboard_entry=paste_and_stop)
    storage = SimpleNamespace(
        local_id="Darwin@192.168.100.64",
        mark_programmatic_clipboard_write=lambda: marks.append(True),
    )

    def fail_get_files(*args, **kwargs):
        raise AssertionError("get_files should not be called for local file entries")

    monkeypatch.setattr(paste_queue_handler.api_module, "get_files", fail_get_files)

    paste_queue_handler.paste_queue_handler(
        stop_event,
        q,
        clipboard,
        storage,
        private_key=None,
        public_key=None,
        key_pass=None,
    )

    assert pasted == [["/tmp/a.txt", "/tmp/b.txt"]]
    assert marks == [True]


def test_remote_file_entry_fetches_files(monkeypatch):
    q = Queue()
    q.put(_make_file_entry("192.168.100.17", [r"C:\a.txt"]))

    fetched = ["/tmp/downloaded.txt"]
    stop_event = Event()
    pasted = []
    marks = []

    def paste_and_stop(paths):
        pasted.append(paths)
        stop_event.set()

    clipboard = SimpleNamespace(paste_clipboard_entry=paste_and_stop)
    storage = SimpleNamespace(
        local_id="Darwin@192.168.100.64",
        mark_programmatic_clipboard_write=lambda: marks.append(True),
    )

    monkeypatch.setattr(
        paste_queue_handler.api_module,
        "get_files",
        lambda paths, ip, public_key, private_key, key_pass: fetched if ip == "192.168.100.17" else [],
    )

    paste_queue_handler.paste_queue_handler(
        stop_event,
        q,
        clipboard,
        storage,
        private_key=None,
        public_key=None,
        key_pass=None,
    )

    assert pasted == [fetched]
    assert marks == [True]
