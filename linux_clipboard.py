import os
import subprocess

from abstract_clipboard import AbstractClipboard


def get_linux_clipboard():
    # xdg=subprocess.check_output(['echo $XDG_SESSION_TYPE'])$XDG_SESSION_TYPE
    xdg=os.environ.get('XDG_SESSION_TYPE')
    if xdg == 'wayland':
        return WaylandClipboard()
    elif xdg == 'x11':
        return X11Clipboard()
    else:
        raise Exception('Unsupported XDG session type')


class WaylandClipboard(AbstractClipboard):

    def __init__(self):
        self._paste_default_clipboard_entry()

    def _paste_default_clipboard_entry(self):
        process = subprocess.Popen(['wl-copy', '--type', 'text/plain'], stdin=subprocess.PIPE, text=True)
        process.stdin.write('')
        process.stdin.close()


    def _check_clipboard_type(self):
        list_of_types = []
        try:
            types = subprocess.check_output(['wl-paste', '-l'], text=True)
            list_of_types = [entry_type.strip() for entry_type in types.splitlines() if entry_type.strip()]
        except subprocess.CalledProcessError as e:
            print(f'{e.cmd} threw an exception: \n\t{e.returncode}\n\t{e.output}')

        if "text/uri-list" in list_of_types:
            return "files"
        elif "text/plain" in list_of_types:
            return "text"
        # ToDo: append with other types like rich text and image snippets
        return "unknown"


    def get_clipboard_entry(self):
        #Text
        output = subprocess.check_output(['wl-paste'])
        clipboard_type = self._check_clipboard_type()
        out = output.decode('utf-8').strip()
        if clipboard_type == "text":
            return clipboard_type, out
        elif clipboard_type == "files":
            file_list = [file.strip() for file in out.splitlines() if file.strip()]
            return clipboard_type, file_list
        return "empty", None

    def paste_clipboard_entry(self):
        pass


class X11Clipboard(AbstractClipboard):

    def _check_clipboard_type(self):
        list_of_types = []
        try:
            types = subprocess.check_output(['xclip', '-selection', 'clipboard', '-t', 'TARGETS', '-o'], text=True)
            list_of_types = [entry_type.strip() for entry_type in types.splitlines() if entry_type.strip()]
        except subprocess.CalledProcessError as e:
            print(f'{e.cmd} threw an exception: \n\t{e.returncode}\n\t{e.output}')

        if "text/uri-list" in list_of_types:
            return "files"
        elif "text/plain" in list_of_types:
            return "text"
        # ToDo: append with other types like rich text and image snippets
        return "unknown"

    def get_clipboard_entry(self):
        output = subprocess.check_output(['xclip', '-selection', 'clipboard', '-o'])
        clipboard_type = self._check_clipboard_type()
        out = output.decode('utf-8').strip()
        if clipboard_type == "text":
            return clipboard_type, out
        elif clipboard_type == "files":
            file_list = [file.strip() for file in out.splitlines() if file.strip()]
            return clipboard_type, file_list
        return "empty", None

    def paste_clipboard_entry(self):
        pass