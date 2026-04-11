"""macOS clipboard via PyObjC ``NSPasteboard``."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import AppKit
from Foundation import NSURL
from abstract_clipboard import AbstractClipboard
from pynput import keyboard

TEXT_TYPES = [
    "public.utf8-plain-text",
    "public.plain-text",
]

class MacClipboard(AbstractClipboard):
    """Read/write text and file URLs from the general pasteboard."""

    def __init__(self):
        """Attach a pynput keyboard controller used to synthesize Cmd+V after updating the pasteboard."""
        self.keyboard_controller = keyboard.Controller()

    def get_clipboard_entry(self):
        """Prefer file URLs, otherwise return the first UTF-8/plain string."""
        pb = AppKit.NSPasteboard.generalPasteboard()

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


    def paste_clipboard_entry(self, entry):
        """Write *entry* to the pasteboard and simulate Cmd+V."""
        pb = AppKit.NSPasteboard.generalPasteboard()

        print(f"Attempting to paste {entry}, which is a {type(entry)}")

        if isinstance(entry, str):
            pb.clearContents()
            pb_updated = pb.setString_forType_(entry, "public.utf8-plain-text")

        elif isinstance(entry, list):
            pb.clearContents()
            urls = [NSURL.fileURLWithPath_(path) for path in entry]
            pb_updated = pb.writeObjects_(urls)

        else:
            print(f"Unsupported entry type: {type(entry)}")
            return

        if pb_updated:
            print(f"Successfully updated {entry}")
            with self.keyboard_controller.pressed(keyboard.Key.cmd):
                self.keyboard_controller.press('v')
                self.keyboard_controller.release('v')
        else:
            print(f"Failed to paste {entry}")