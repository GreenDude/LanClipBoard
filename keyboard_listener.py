from __future__ import annotations

from queue import Queue
from threading import Event, Thread
from pynput import keyboard
import time

from clipboard_storage import ClipboardStorage

# PASTE_HOTKEY = {"Key.cmd", "Key.shift", "v"}  # Cmd+Shift+V. TODO: Read from config
PASTE_HOTKEY = {"Key.ctrl", "Key.shift", "v"}  # ctrl+Shift+V. TODO: Read from config


def normalize_key(key) -> str:
    if hasattr(key, "char") and key.char:
        if len(key.char) == 0 and 1<=ord(key.char)<=26:
            return str(ord(key.char) + 96)
        return key.char.lower()
    key_str = str(key)
    if "_" in key_str:
        key_str = key_str[:key_str.index("_")]
    return key_str

def monitor_keyboard(stop_event: Event,
                     paste_queue: Queue,
                     clipboard_storage: ClipboardStorage,
                     is_pasting: bool
                     ) -> None:
    pressed = set()

    def on_press(key):
        nonlocal is_pasting
        k = normalize_key(key)

        pressed.add(k)
        print(pressed)

        if PASTE_HOTKEY <= pressed:
            print("YAY (paste hotkey)")
            if not is_pasting:
                paste_queue.put(clipboard_storage.get_latest_clipboard_entry())
                is_pasting= True
            print(paste_queue.qsize())

    def on_release(key):
        nonlocal is_pasting
        k = normalize_key(key)
        pressed.discard(k)
        if k in PASTE_HOTKEY:
            is_pasting = False

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    # Wait until stop_event, then stop listener
    while not stop_event.is_set():
        time.sleep(0.1)

    listener.stop()
    listener.join()
