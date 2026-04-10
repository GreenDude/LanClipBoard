"""Tests for :mod:`clipboard_factory`."""

import pytest

import clipboard_factory


def test_unsupported_platform_raises(monkeypatch):
    monkeypatch.setattr(clipboard_factory.platform, "system", lambda: "TempleOS")
    with pytest.raises(RuntimeError, match="Unsupported platform"):
        clipboard_factory.get_clipboard()
