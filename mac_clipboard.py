import AppKit
from Foundation import NSURL
from abstract_clipboard import AbstractClipboard

TEXT_TYPES = [
    "public.utf8-plain-text",
    "public.plain-text",
]

class MacClipboard(AbstractClipboard):


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


    def paste_clipboard_entry(self):
        pass