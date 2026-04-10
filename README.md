# The why

Let's imagine you work on several devices on the same network, and eventually you need to copy and paste something between them.
Using a messaging app or some cloud storage might solve that; however, it's a bit annoying to copy-paste text and files too often.

This tool provides a simple and secure way to share your clipboard across multiple devices on the same network.

# Supported Operating Systems

- Windows
- macOS
- Linux (Wayland)
- Linux X11 (To be tested)

# How to use

1. Install the latest version of python
2. Clone the repository
3. Install the required dependencies using `pip install` *to be updated*
4. Run the application config using `config_ui.py`
5. For the first run highly recommend pressing the `Restore to defaults` button to ensure proper key mapping
6. Press the `Start` button to begin sharing your clipboard
7. The application will start will make the device discoverable on the network for other devices running the similarly configured Lan Clipboard
8. As soon as the first handshake passes, a shared clipboard will be available
9. Use the configured shortcut to paste text and files (Ctrl + Shift + V on Windows, Cmd + Shift + V on Mac) or just regular Ctlr + V on Wayland 
10. Press the `Stop` button to stop sharing your clipboard 

**Feature Set**

✅ Cross-platform clipboard

✅ Sharing on LAN

✅ File Transfer

✅ Windows paste

✅ Read shortcut from config on startup

✅ Linux Wayland paste

✅ Linux X11 paste

✅ Request and Response Body Security

✅ Secure file transfer

✅ Available devices discovery (via secure handshake?)

**Known issues**

☢️ Wayland flickering

☢️ Restarting after a handshake results in discovery failure (as the device is already known by others)

☢️ Windows File transfer saves the file in `AddData/Local/Temp/LanClipboard`

**Potential issues**

⚠️KDE not tested

⚠️X11 Not tested

⚠️Potential compatibility issues with unexpected Linux Desktop Environments

⚠️To check with 2 Wayland devices (might go into a clipboard update loop)