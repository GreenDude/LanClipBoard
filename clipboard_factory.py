import platform

supported_platform = ('Darwin',)

def get_clipboard():
    ptfrm = platform.system()
    try:
        ptfrm in supported_platform
    except:
        raise Exception('Unsupported platform')

    if ptfrm == 'Darwin':
        from mac_clipboard import MacClipboard
        return MacClipboard()
    elif ptfrm == 'Windows':
        from windows_clipboard import WindowsClipboard
        return WindowsClipboard()
    return None