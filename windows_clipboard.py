"""Windows clipboard via ``pywin32`` and optional synthetic Ctrl+V."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import os
import struct
import time
from pathlib import Path

import win32clipboard
import win32con
from pynput import keyboard

from abstract_clipboard import AbstractClipboard


class WindowsClipboard(AbstractClipboard):
    """Unicode text and ``CF_HDROP`` file lists."""

    def __init__(self):
        """Prepare a pynput keyboard controller for post-update paste."""
        self.keyboard_controller = keyboard.Controller()

    def open_clipboard_safely(self, number_of_retries=5, delay=0.1):
        """Retry ``OpenClipboard`` when another app holds the clipboard."""
        for _ in range(number_of_retries):
            try:
                win32clipboard.OpenClipboard()
                return True
            except Exception:
                time.sleep(delay)

        return False

    def get_clipboard_entry(self):
        """Return Unicode text or a stringified list of dropped file paths."""
        _clipboard_opened = self.open_clipboard_safely()
        if _clipboard_opened:
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    return "text", win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                elif win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP):
                    path_list = list(win32clipboard.GetClipboardData(win32clipboard.CF_HDROP))
                    normalized_list = [Path(p).as_posix() for p in path_list]
                    return "files", str(normalized_list)
            finally:
                win32clipboard.CloseClipboard()

        return ("empty", None)


    def paste_clipboard_entry(self, entry):
        """Set clipboard content then send Ctrl+V when the update succeeds."""
        print(f"Attempting to paste {entry}, which is a {type(entry)}")

        if not self.open_clipboard_safely():
            print("Failed to open clipboard")
            return

        try:
            win32clipboard.EmptyClipboard()

            if isinstance(entry, str):
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, entry)
                clipboard_updated = True

            elif isinstance(entry, list):
                paths = [os.path.normpath(p) for p in entry if p]
                if not paths:
                    print("No valid file paths to paste")
                    clipboard_updated = False
                else:
                    # CF_HDROP expects a DROPFILES struct followed by a UTF-16LE
                    # double-NUL-terminated file list.
                    file_list = "\0".join(paths) + "\0\0"
                    dropfiles_header = struct.pack("IiiII", 20, 0, 0, 0, 1)
                    dropfiles_payload = dropfiles_header + file_list.encode("utf-16le")
                    win32clipboard.SetClipboardData(win32con.CF_HDROP, dropfiles_payload)
                    clipboard_updated = True

            else:
                print(f"Unsupported entry type: {type(entry)}")
                clipboard_updated = False

        finally:
            win32clipboard.CloseClipboard()

        if clipboard_updated:
            print(f"Successfully updated clipboard with {entry}")

            time.sleep(0.05)  # allow clipboard to settle

            with self.keyboard_controller.pressed(keyboard.Key.ctrl):
                self.keyboard_controller.press('v')
                self.keyboard_controller.release('v')

        else:
            print(f"Failed to paste {entry}")