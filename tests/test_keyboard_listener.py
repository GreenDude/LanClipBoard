"""Tests for :mod:`keyboard_listener` helpers."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
from keyboard_listener import _parse_win32_hotkey_for_suppress, _sync_win32_modifier_tokens


def test_parse_win32_hotkey_ctrl_shift_v():
    mods, vks = _parse_win32_hotkey_for_suppress({"Key.ctrl", "Key.shift", "v"})
    assert mods == {"ctrl", "shift"}
    assert vks == {0x56}


def test_parse_win32_hotkey_preserves_cmd_alt():
    mods, vks = _parse_win32_hotkey_for_suppress({"Key.cmd", "Key.alt", "x"})
    assert mods == {"cmd", "alt"}
    assert vks == {0x58}


def test_parse_win32_hotkey_supports_insert():
    mods, vks = _parse_win32_hotkey_for_suppress({"Key.ctrl", "Key.shift", "Key.insert"})
    assert mods == {"ctrl", "shift"}
    assert vks == {0x2D}


def test_sync_win32_modifier_tokens_adds_and_removes(monkeypatch):
    states = {
        0x11: True,   # ctrl
        0x10: False,  # shift
        0x12: True,   # alt
        0x5B: False,  # left win
        0x5C: False,  # right win
    }
    monkeypatch.setattr("keyboard_listener._win32_get_key_state", lambda vk: states[vk])

    pressed = {"Key.shift", "v"}
    synced = _sync_win32_modifier_tokens(pressed)

    assert synced == {"Key.ctrl", "Key.alt", "v"}
