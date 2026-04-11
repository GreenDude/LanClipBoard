"""Select a platform-specific clipboard implementation."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import platform

supported_platform = ("Darwin", "Windows", "Linux")


def get_clipboard():
    """Return an `AbstractClipboard` for the current OS, or raise if unsupported."""
    ptfrm = platform.system()
    if ptfrm not in supported_platform:
        raise RuntimeError(f"Unsupported platform: {ptfrm!r}")

    if ptfrm == "Darwin":
        from mac_clipboard import MacClipboard
        return MacClipboard()
    elif ptfrm == 'Windows':
        from windows_clipboard import WindowsClipboard
        return WindowsClipboard()
    elif ptfrm == "Linux":
        from linux_clipboard import get_linux_clipboard

        return get_linux_clipboard()
    raise RuntimeError(f"Clipboard not implemented for platform: {ptfrm!r}")