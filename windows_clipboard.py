import time

import win32clipboard

from abstract_clipboard import AbstractClipboard


class WindowsClipboard(AbstractClipboard):


    def open_clipboard_safely(self, number_of_retries = 5, delay = 0.1):
        print("open_clipboard_safely")
        for _ in range(number_of_retries):
            try:
                win32clipboard.OpenClipboard()
                print("the clipboard is opened")
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
                    return "files", list(win32clipboard.GetClipboardData(win32clipboard.CF_HDROP))
            finally:
                win32clipboard.CloseClipboard()

        return ("empty", None)



    def paste_clipboard_entry(self):
        pass