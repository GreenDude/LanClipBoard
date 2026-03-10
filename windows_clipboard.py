import time
import os

import win32clipboard
from pynput import keyboard

from abstract_clipboard import AbstractClipboard


class WindowsClipboard(AbstractClipboard):

    def __init__(self):
        self.keyboard_controller = keyboard.Controller()


    def open_clipboard_safely(self, number_of_retries = 5, delay = 0.1):
        for _ in range(number_of_retries):
            try:
                win32clipboard.OpenClipboard()
                return True
            except:
                time.sleep(delay)

        return False



    def get_clipboard_entry(self):
        _clipboard_opened = self.open_clipboard_safely()
        if _clipboard_opened:
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    return "text", win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                elif win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP):
                    path_list = list(win32clipboard.GetClipboardData(win32clipboard.CF_HDROP))
                    normalized_list = [os.path.normpath(p) for p in path_list]
                    return "files", str(normalized_list)
            finally:
                win32clipboard.CloseClipboard()

        return ("empty", None)


    def paste_clipboard_entry(self, entry):
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
                # CF_HDROP expects a double-null-terminated string list
                paths = [os.path.normpath(p) for p in entry]
                drop_files = "\0".join(paths) + "\0\0"
                win32clipboard.SetClipboardData(win32con.CF_HDROP, drop_files)
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