from abc import ABC, abstractmethod

class AbstractClipboard(ABC):

    @abstractmethod
    def get_clipboard_entry(self):
        pass


    @abstractmethod
    def paste_clipboard_entry(self):
        pass