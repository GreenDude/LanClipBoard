"""Tests for :mod:`clipboard_storage` validation and storage behavior."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from clipboard_storage import ClipboardEntry, ClipboardStorage, _new_entry_is_valid


def _entry(**kwargs) -> ClipboardEntry:
    defaults = dict(
        origin="remote",
        platform="Linux",
        type="text",
        entry="hello",
        timestamp=datetime.now(UTC),
    )
    defaults.update(kwargs)
    return ClipboardEntry(**defaults)


def test_new_entry_is_valid_requires_nonempty_entry():
    assert _new_entry_is_valid(_entry(entry="x")) is True
    assert _new_entry_is_valid(_entry(entry="")) is False


def test_new_entry_is_valid_type_and_platform():
    assert _new_entry_is_valid(_entry(type="files")) is True
    assert _new_entry_is_valid(_entry(type="image")) is False
    assert _new_entry_is_valid(_entry(platform="Plan9")) is False


def test_store_rejects_invalid_entry():
    storage = ClipboardStorage("local@10.0.0.1")
    pq = MagicMock()
    bad = _entry(type="bad", entry="x")
    assert storage.store_clipboard_entry("10.0.0.2", bad, pq) is False
    pq.put.assert_not_called()


def test_store_wayland_enqueues_remote_entry(monkeypatch):
    monkeypatch.setattr("clipboard_storage._is_wayland", True)
    storage = ClipboardStorage("local@10.0.0.1")
    pq = MagicMock()
    remote = _entry(origin="10.0.0.2", platform="Linux", type="text", entry="hi")
    assert storage.store_clipboard_entry("10.0.0.2", remote, pq) is True
    pq.put.assert_called_once()


def test_store_wayland_skips_local_origin(monkeypatch):
    monkeypatch.setattr("clipboard_storage._is_wayland", True)
    storage = ClipboardStorage("local@10.0.0.1")
    pq = MagicMock()
    local = _entry(origin="local@10.0.0.1", platform="Linux", type="text", entry="hi")
    assert storage.store_clipboard_entry("local@10.0.0.1", local, pq) is True
    pq.put.assert_not_called()
