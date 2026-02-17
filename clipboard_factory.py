import platform
from mac_clipboard import MacClipboard

supported_platform = ('Darwin',)

def get_clipboard():
    ptfrm = platform.system()
    try:
        ptfrm in supported_platform
    except:
        raise Exception('Unsupported platform')

    if ptfrm == 'Darwin':
        return MacClipboard()
    return None