"""Linux clipboard via ``wl-clipboard`` (Wayland) or ``xclip`` (X11)."""

import os
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from abstract_clipboard import AbstractClipboard


def get_linux_clipboard():
    """Return :class:`WaylandClipboard` or :class:`X11Clipboard` based on ``XDG_SESSION_TYPE``."""
    xdg = os.environ.get("XDG_SESSION_TYPE")
    if xdg == "wayland":
        return WaylandClipboard()
    elif xdg == "x11":
        return X11Clipboard()
    else:
        raise Exception("Unsupported XDG session type")


def _build_uri_list(paths: list[str]) -> str:
    """Format *paths* as a ``text/uri-list`` body."""
    uris = []
    for path in paths:
        resolved = Path(path).expanduser().resolve()
        uris.append("file://" + quote(str(resolved)))
    return "\n".join(uris) + "\n"


def _build_gnome_copied_files(paths: list[str], mode: str = "copy") -> str:
    """Build ``x-special/gnome-copied-files`` payload for *paths*."""
    return mode + "\n" + _build_uri_list(paths)


def _parse_uri_list(data: str) -> list[str]:
    """Parse ``file://`` lines from a URI list string."""
    paths = []
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("file://"):
            parsed = urlparse(line)
            paths.append(unquote(parsed.path))
    return paths


def _parse_gnome_copied_files(data: str) -> tuple[str, list[str]]:
    """Split gnome-copied-files payload into *(mode, paths)*."""
    lines = [line.strip() for line in data.splitlines() if line.strip()]
    if not lines:
        return "copy", []

    mode = lines[0] if lines[0] in ("copy", "cut") else "copy"
    uri_lines = lines[1:] if lines[0] in ("copy", "cut") else lines
    return mode, _parse_uri_list("\n".join(uri_lines))


class WaylandClipboard(AbstractClipboard):
    """Clipboard integration using ``wl-paste`` / ``wl-copy``."""

    def _check_clipboard_type(self):
        """Return ``files``, ``text``, or ``unknown`` from ``wl-paste -l``."""
        list_of_types = []
        try:
            types = subprocess.check_output(["wl-paste", "-l"], text=True)
            list_of_types = [entry_type.strip() for entry_type in types.splitlines() if entry_type.strip()]
            # print (f"Recorded types: \n {list_of_types}")
        except subprocess.CalledProcessError as e:
            print(f"{e.cmd} threw an exception: \n\t{e.returncode}\n\t{e.output}")
        except FileNotFoundError:
            print("wl-paste not found")
            return "unknown"

        if "x-special/gnome-copied-files" in list_of_types or "text/uri-list" in list_of_types:
            return "files"
        elif "text/plain" in list_of_types or any(t.startswith("text/plain") for t in list_of_types):
            return "text"
        return "unknown"

    def get_clipboard_entry(self):
        """Read text or file URI list from the Wayland clipboard."""
        clipboard_type = self._check_clipboard_type()

        try:
            if clipboard_type == "text":
                output = subprocess.check_output(
                    ["wl-paste"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                return "text", output.strip()

            elif clipboard_type == "files":
                output = subprocess.check_output(
                    ["wl-paste", "-t", "text/uri-list"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                file_list = _parse_uri_list(output)
                if file_list:
                    return "files", str(file_list)

        except subprocess.CalledProcessError:
            pass
        except FileNotFoundError:
            print("wl-paste not found")

        return "empty", None

    def paste_clipboard_entry(self, entry):
        """Push *entry* to the clipboard using ``wl-copy``."""
        print(f"Attempting to paste {entry}, which is a {type(entry)}")

        if isinstance(entry, str):
            proc = subprocess.Popen(
                ["wl-copy", "-t", "text/plain;charset=utf-8"],
                stdin=subprocess.PIPE,
                text=True,
            )
            proc.communicate(entry)

            if proc.returncode == 0:
                print(f"Successfully updated clipboard with text: {entry}")
            else:
                print(f"Failed to paste {entry}")
            return

        if isinstance(entry, list):

            uri_list = _build_uri_list(entry)

            proc = subprocess.Popen(
                ["wl-copy", "-t", "text/uri-list"],
                stdin=subprocess.PIPE,
                text = True
            )

            proc.communicate(uri_list)

            if proc.returncode == 0:
                print(f"Successfully updated clipboard with files: {entry}")
            else:
                print(f"Failed to paste {entry}")
            return

        print(f"Unsupported entry type: {type(entry)}")
        raise NotImplementedError


class X11Clipboard(AbstractClipboard):
    """Clipboard integration using ``xclip``."""

    def _check_clipboard_type(self):
        """Return ``files``, ``text``, or ``unknown`` from ``TARGETS``."""
        list_of_types = []
        try:
            types = subprocess.check_output(
                ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
                text=True
            )
            list_of_types = [entry_type.strip() for entry_type in types.splitlines() if entry_type.strip()]
        except subprocess.CalledProcessError as e:
            print(f"{e.cmd} threw an exception: \n\t{e.returncode}\n\t{e.output}")
        except FileNotFoundError:
            print("xclip not found")
            return "unknown"

        if "x-special/gnome-copied-files" in list_of_types or "text/uri-list" in list_of_types:
            return "files"
        elif "text/plain" in list_of_types or "UTF8_STRING" in list_of_types:
            return "text"
        return "unknown"

    def get_clipboard_entry(self):
        """Read text or files from the X11 clipboard."""
        clipboard_type = self._check_clipboard_type()

        try:
            if clipboard_type == "text":
                output = subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], text=True)
                return "text", output.strip()

            elif clipboard_type == "files":
                try:
                    output = subprocess.check_output(
                        ["xclip", "-selection", "clipboard", "-t", "x-special/gnome-copied-files", "-o"],
                        text=True
                    )
                    _, file_list = _parse_gnome_copied_files(output)
                    if file_list:
                        return "files", str(file_list)
                except subprocess.CalledProcessError:
                    pass

                try:
                    output = subprocess.check_output(
                        ["xclip", "-selection", "clipboard", "-t", "text/uri-list", "-o"],
                        text=True
                    )
                    file_list = _parse_uri_list(output)
                    if file_list:
                        return "files", str(file_list)
                except subprocess.CalledProcessError:
                    pass

        except FileNotFoundError:
            print("xclip not found")

        return "empty", None

    def paste_clipboard_entry(self, entry):
        """Write *entry* to the X11 clipboard (URI list + optional gnome metadata)."""
        print(f"Attempting to paste {entry}, which is a {type(entry)}")

        if isinstance(entry, str):
            subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "text/plain", "-i"],
                input=entry,
                text=True,
                check=True,
            )
            print(f"Successfully updated clipboard with text: {entry}")
            return

        if isinstance(entry, list):
            uri_list = _build_uri_list(entry)
            gnome_payload = _build_gnome_copied_files(entry, mode="copy")

            subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "text/uri-list", "-i"],
                input=uri_list,
                text=True,
                check=True,
            )

            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", "x-special/gnome-copied-files", "-i"],
                    input=gnome_payload,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError:
                pass

            print(f"Successfully updated clipboard with files: {entry}")
            return

        print(f"Unsupported entry type: {type(entry)}")
        raise NotImplementedError