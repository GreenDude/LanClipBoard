Let's imagine you work on several devices on the same network, and eventually you need to copy and paste something between them.
Could you use a messaging app or something else? You could... but that would be a bit annoying to copy-paste stuff too often.

This is exactly the annoyance I ran into, which is why I created this project.

TBC...

**Feature Set**

✅ Cross-platform clipboard

✅ Sharing on LAN

✅ File Transfer

✅ Windows paste

☑️ Read shortcut from config on startup

✅ Linux Wayland paste

✅ Linux X11 paste

☑️ Security

☑️ Available devices discovery (via secure handshake?)

**Known issues**

☢️ Files are saved in project root for now

☢️ Windows CTRL + Shift + V causes double paste

**Potential issues**

⚠️KDE not tested

⚠️X11 Not tested

⚠️Potential compatibility issues with unexpected Linux Desktop Environments

⚠️To check with 2 Wayland devices (might go into a clipboard update loop)