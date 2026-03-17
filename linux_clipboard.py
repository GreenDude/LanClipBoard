import os
import subprocess
from pathlib import Path
from urllib.parse import quote, urlparse, unquote

from abstract_clipboard import AbstractClipboard


def get_linux_clipboard():
    xdg = os.environ.get("XDG_SESSION_TYPE")
    if xdg == "wayland":
        return WaylandClipboard()
    elif xdg == "x11":
        return X11Clipboard()
    else:
        raise Exception("Unsupported XDG session type")


def _build_uri_list(paths: list[str]) -> str:
    uris = []
    for path in paths:
        resolved = Path(path).expanduser().resolve()
        uris.append("file://" + quote(str(resolved)))
    return "\n".join(uris) + "\n"


def _build_gnome_copied_files(paths: list[str], mode: str = "copy") -> str:
    return mode + "\n" + _build_uri_list(paths)


def _parse_uri_list(data: str) -> list[str]:
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
    lines = [line.strip() for line in data.splitlines() if line.strip()]
    if not lines:
        return "copy", []

    mode = lines[0] if lines[0] in ("copy", "cut") else "copy"
    uri_lines = lines[1:] if lines[0] in ("copy", "cut") else lines
    return mode, _parse_uri_list("\n".join(uri_lines))


class WaylandClipboard(AbstractClipboard):

    def _check_clipboard_type(self):
        list_of_types = []
        try:
            types = subprocess.check_output(["wl-paste", "-l"], text=True)
            list_of_types = [entry_type.strip() for entry_type in types.splitlines() if entry_type.strip()]
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
        clipboard_type = self._check_clipboard_type()

        try:
            if clipboard_type == "text":
                output = subprocess.check_output(["wl-paste"], text=True)
                return "text", output.strip()

            elif clipboard_type == "files":
                # Prefer GNOME format first on Wayland
                try:
                    output = subprocess.check_output(
                        ["wl-paste", "-t", "x-special/gnome-copied-files"],
                        text=True
                    )
                    _, file_list = _parse_gnome_copied_files(output)
                    if file_list:
                        return "files", str(file_list)
                except subprocess.CalledProcessError:
                    pass

                try:
                    output = subprocess.check_output(
                        ["wl-paste", "-t", "text/uri-list"],
                        text=True
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
            # On Wayland, one wl-copy process owns one clipboard payload.
            # Setting both formats one after another is unreliable because the
            # second one replaces the first clipboard owner.
            # For GNOME/Files on Wayland, prefer x-special/gnome-copied-files.
            gnome_payload = _build_gnome_copied_files(entry, mode="copy")

            proc = subprocess.Popen(
                ["wl-copy", "-t", "x-special/gnome-copied-files"],
                stdin=subprocess.PIPE,
                text=True,
            )
            proc.communicate(gnome_payload)

            if proc.returncode == 0:
                print(f"Successfully updated clipboard with files: {entry}")
            else:
                print(f"Failed to paste {entry}")
            return

        print(f"Unsupported entry type: {type(entry)}")
        raise NotImplementedError


class X11Clipboard(AbstractClipboard):

    def _check_clipboard_type(self):
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