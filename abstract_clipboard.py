from abc import ABC, abstractmethod

from clipboard_storage import ClipboardEntry


class AbstractClipboard(ABC):

    @abstractmethod
    def get_clipboard_entry(self):
        pass


    @abstractmethod
    def paste_clipboard_entry(self, entry):
        pass