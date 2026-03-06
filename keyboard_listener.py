from __future__ import annotations

from queue import Queue
from threading import Event, Thread
from pynput import keyboard
import time

from clipboard_storage import ClipboardStorage

PASTE_HOTKEY = {"Key.cmd", "Key.shift", "v"}  # Cmd+Shift+V. TODO: Read from config

def normalize_key(key) -> str:
    if hasattr(key, "char") and key.char:
        return key.char.lower()
    return str(key)

def monitor_keyboard(stop_event: Event, paste_queue: Queue, clipboard_storage: ClipboardStorage):
    pressed = set()

    def on_press(key):
        k = normalize_key(key)
        pressed.add(k)

        if PASTE_HOTKEY <= pressed:
            print("YAY (paste hotkey)")
            # TODO: trigger paste action here
            paste_queue.put(clipboard_storage.get_latest_clipboard_entry())
            print(paste_queue.qsize())
            print(paste_queue.get())

        # Optional debug:
        # print("pressed:", pressed)

    def on_release(key):
        k = normalize_key(key)
        pressed.discard(k)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    # Wait until stop_event, then stop listener
    while not stop_event.is_set():
        time.sleep(0.1)

    listener.stop()
    listener.join()
