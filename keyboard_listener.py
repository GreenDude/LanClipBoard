"""Global hotkey listener: when the configured combo is held, enqueue the latest clipboard entry."""

from __future__ import annotations

import platform
import time
from queue import Queue
from threading import Event
from typing import Callable

from pynput import keyboard

from clipboard_storage import ClipboardStorage

# Windows low-level hook: suppress physical hotkey so the focused app does not also handle
# Ctrl+Shift+V (etc.), which would paste once natively and again after our synthetic Ctrl+V.
_WM_KEYDOWN = 0x0100
_WM_SYSKEYDOWN = 0x0104
_LLKHF_INJECTED = 0x10
_VK_SHIFT = 0x10
_VK_CONTROL = 0x11
_VK_MENU = 0x12
_VK_LWIN = 0x5B
_VK_RWIN = 0x5C


def _win32_get_key_state(vk: int) -> bool:
    import ctypes

    return bool(ctypes.windll.user32.GetKeyState(vk) & 0x8000)


def _parse_win32_hotkey_for_suppress(paste_hotkey: set[str]) -> tuple[set[str], set[int]]:
    """Split config tokens into modifier names and trigger virtual-key codes (for suppression)."""
    mods: set[str] = set()
    vks: set[int] = set()
    for token in paste_hotkey:
        if token == "Key.ctrl":
            mods.add("ctrl")
        elif token == "Key.shift":
            mods.add("shift")
        elif token == "Key.alt":
            mods.add("alt")
        elif token == "Key.alt_gr":
            mods.add("alt_gr")
        elif token in ("Key.cmd", "Key.cmd_l", "Key.cmd_r"):
            mods.add("cmd")
        elif len(token) == 1 and token.isalpha():
            vks.add(ord(token.upper()))
    return mods, vks


def _win32_modifiers_satisfied(required: set[str]) -> bool:
    if "ctrl" in required and not _win32_get_key_state(_VK_CONTROL):
        return False
    if "shift" in required and not _win32_get_key_state(_VK_SHIFT):
        return False
    if "alt" in required and not _win32_get_key_state(_VK_MENU):
        return False
    if "alt_gr" in required and not _win32_get_key_state(_VK_MENU):
        return False
    if "cmd" in required and not (
        _win32_get_key_state(_VK_LWIN) or _win32_get_key_state(_VK_RWIN)
    ):
        return False
    return True


def _make_win32_suppress_hotkey_filter(
    paste_hotkey: set[str],
    listener_ref: list,
) -> Callable:
    """Return a ``win32_event_filter`` that swallows the real chord but not pynput-injected keys."""
    required_mods, trigger_vks = _parse_win32_hotkey_for_suppress(paste_hotkey)

    def win32_event_filter(msg, data) -> bool:
        if not trigger_vks or listener_ref[0] is None:
            return True
        if msg not in (_WM_KEYDOWN, _WM_SYSKEYDOWN):
            return True
        flags = int(getattr(data, "flags", 0))
        if flags & _LLKHF_INJECTED:
            return True
        vk = int(getattr(data, "vkCode", 0)) & 0xFF
        if vk not in trigger_vks:
            return True
        if not _win32_modifiers_satisfied(required_mods):
            return True
        listener_ref[0].suppress_event()
        return True

    return win32_event_filter


def normalize_key(key) -> str:
    """Map a pynput *key* to a lowercase token comparable to configured hotkey strings."""
    if hasattr(key, "char") and key.char:
        if len(key.char) == 1 and 1 <= ord(key.char) <= 26:
            return chr(ord(key.char) + 96)
        return key.char.lower()
    key_str = str(key)

    # Handle <86> style VK codes. Because Ctrl + Alt + V is <86>
    if key_str.startswith("<") and key_str.endswith(">"):
        try:
            vk = int(key_str[1:-1])
            if 65 <= vk <= 90:  # A-Z
                return chr(vk).lower()
        except ValueError:
            pass

    if "_" in key_str:
        key_str = key_str[:key_str.index("_")]
    return key_str


def monitor_keyboard(
    stop_event: Event,
    paste_queue: Queue,
    clipboard_storage: ClipboardStorage,
    paste_hotkey: set[str],
) -> None:
    """Listen for *paste_hotkey* and push :meth:`ClipboardStorage.get_latest_clipboard_entry` to *paste_queue*.

    On Windows, a low-level hook suppresses the **physical** chord (e.g. Ctrl+Shift+V) so the focused
    app cannot handle it at the same time as our synthetic Ctrl+V paste (which caused double paste).
    Injected keystrokes from :class:`pynput.keyboard.Controller` are not suppressed.
    """
    pressed = set()
    combo_active = False

    def on_press(key):
        """Track keys and enqueue the latest clipboard snapshot when the hotkey chord completes."""
        nonlocal combo_active
        k = normalize_key(key)

        pressed.add(k)
        print(pressed)
        print(paste_hotkey)

        if paste_hotkey <= pressed and not combo_active:
            paste_queue.put(clipboard_storage.get_latest_clipboard_entry())
            combo_active = True
            print(paste_queue.qsize())

    def on_release(key):
        """Drop released keys and allow the chord to retrigger once modifiers change."""
        nonlocal combo_active
        k = normalize_key(key)
        pressed.discard(k)
        if not (paste_hotkey <= pressed):
            combo_active = False

    listener_ref: list = [None]
    listener_kwargs: dict = {}
    if platform.system() == "Windows":
        listener_kwargs["win32_event_filter"] = _make_win32_suppress_hotkey_filter(
            paste_hotkey,
            listener_ref,
        )

    listener = keyboard.Listener(on_press=on_press, on_release=on_release, **listener_kwargs)
    listener_ref[0] = listener
    listener.start()

    # Wait until stop_event, then stop listener
    while not stop_event.is_set():
        time.sleep(0.1)

    listener.stop()
    listener.join()
