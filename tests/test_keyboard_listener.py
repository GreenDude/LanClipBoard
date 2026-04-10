"""Tests for :mod:`keyboard_listener` helpers."""

from keyboard_listener import _parse_win32_hotkey_for_suppress


def test_parse_win32_hotkey_ctrl_shift_v():
    mods, vks = _parse_win32_hotkey_for_suppress({"Key.ctrl", "Key.shift", "v"})
    assert mods == {"ctrl", "shift"}
    assert vks == {0x56}


def test_parse_win32_hotkey_preserves_cmd_alt():
    mods, vks = _parse_win32_hotkey_for_suppress({"Key.cmd", "Key.alt", "x"})
    assert mods == {"cmd", "alt"}
    assert vks == {0x58}
