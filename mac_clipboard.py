import AppKit
from Foundation import NSURL
from abstract_clipboard import AbstractClipboard
from pynput import keyboard

TEXT_TYPES = [
    "public.utf8-plain-text",
    "public.plain-text",
]

class MacClipboard(AbstractClipboard):

    def __init__(self):
        self.keyboard_controller = keyboard.Controller()


    def get_clipboard_entry(self):
        pb = AppKit.NSPasteboard.generalPasteboard()

        # files first
        urls = pb.readObjectsForClasses_options_([NSURL], None)
        if urls:
            paths = [u.path() for u in urls if getattr(u, "isFileURL", lambda: False)()]
            if paths:
                return "files", str(paths)

        # then text
        for t in TEXT_TYPES:
            s = pb.stringForType_(t)
            if s:
                return "text", str(s)

        return "empty", None


    def paste_clipboard_entry(self, enty):
        pb = AppKit.NSPasteboard.generalPasteboard()
        pb_updated = pb.writeObjects_([enty])
        if pb_updated:
            with self.keyboard_controller.pressed(keyboard.Key.cmd):
                self.keyboard_controller.press('v')
                self.keyboard_controller.release('v')

        else:
            print(f"Failed to paste {enty}")
