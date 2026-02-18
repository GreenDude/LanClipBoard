import subprocess

from abstract_clipboard import AbstractClipboard


def _check_clipboard_type():
    list_of_types = []
    try:
        types = subprocess.check_output(['wl-paste', '-l'], text=True)
        list_of_types = [entry_type.strip() for entry_type in types.splitlines() if entry_type.strip()]
    except subprocess.CalledProcessError as e:
        print (f'{e.cmd} threw an exception: \n\t{e.returncode}\n\t{e.output}')

    if "text/uri-list" in list_of_types:
        return "files"
    elif "text/plain" in list_of_types:
        return "text"
    #ToDo: append with other types like rich text and image snippets
    return "unknown"


class LinuxClipboard(AbstractClipboard):

    def get_clipboard_entry(self):
        #Text
        output = subprocess.check_output(['wl-paste'])
        clipboard_type = _check_clipboard_type()
        out = output.decode('utf-8').strip()
        if clipboard_type == "text":
            return clipboard_type, out
        elif clipboard_type == "files":
            file_list = [file.strip() for file in out.splitlines() if file.strip()]
            return clipboard_type, file_list
        return "empty", None

    def paste_clipboard_entry(self):
        pass