"""Abstract clipboard backend used by the monitor and paste worker threads."""

from abc import ABC, abstractmethod


class AbstractClipboard(ABC):
    """Platform-specific clipboard adapter (text, files, or empty)."""

    @abstractmethod
    def get_clipboard_entry(self):
        """Return ``(kind, value)`` where *kind* is ``\"text\"``, ``\"files\"``, or ``\"empty\"``."""

    @abstractmethod
    def paste_clipboard_entry(self, entry):
        """Place *entry* (string or path list) on the system clipboard and trigger paste where applicable."""