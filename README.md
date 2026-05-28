# LanClipboard

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## 🚀 Overview

LanClipboard is a **cross-platform LAN clipboard and file sharing tool**.

It allows you to:
- Copy text or files on one device
- Paste them instantly on another device
- Stay fully within your local network (no cloud)

---

## ⚡ Features

- Clipboard sync across devices
- File transfer over LAN
- Peer discovery (mDNS)
- Hotkey-triggered paste
- Optional encryption (JWE + Fernet)
- GUI configuration tool

For the usage guide, please refer to [USAGE.md](docs/USAGE.md)

---

## 🧠 Architecture

```
+-------------------+
| Clipboard Listener|
+--------+----------+
         |
         v
+-------------------+
| Local Storage     |
+--------+----------+
         |
         v
+-------------------+      +-------------------+
| FastAPI Server    | <--> | Peer Devices      |
+-------------------+      +-------------------+

         ^
         |
+-------------------+
| Keyboard Listener |
+-------------------+
```

---

## 📦 Installation

Choose the requirements file for your OS. This project is cross-platform, but the clipboard backend dependencies are not.

### Linux
```bash
git clone <repo>
cd LanClipBoard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-linux.txt
```

Linux also needs clipboard tools installed on the system:

```bash
# Wayland
sudo apt install wl-clipboard

# X11
sudo apt install xclip
```

On Fedora, you may also need build dependencies before `pip install` succeeds:

```bash
sudo dnf install python3-devel gcc kernel-headers wl-clipboard xclip
```

### macOS
```bash
git clone <repo>
cd LanClipBoard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-macos.txt
```

### Windows
```powershell
git clone <repo>
cd LanClipBoard
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-windows.txt
```

For tests, install your OS-specific requirements first, then:

```bash
pip install -r requirements-dev.txt
```

---

## ▶️ Usage

The app is served through `uvicorn`, not `python main.py`.

### Start the server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Optional config UI
If you want to edit `config/config.yaml` and launch the server from a GUI:

```bash
python config_ui.py
```

The config UI starts `uvicorn main:app` under the hood.

---

## ⌨️ Default Shortcuts

| OS        | Shortcut            |
|----------|--------------------|
| Windows  | Ctrl + Shift + V   |
| macOS    | Cmd + Shift + V    |
| Wayland  | Ctrl + V           |

---

## 🔐 Security

- Optional encryption enabled via config
- Uses RSA + Fernet
- Designed for trusted LAN environments

For more details please refer to [SECURITY.md](docs/SECURITY.md)

---

## 📡 API Examples

### Handshake
```http
POST /api/handshake
```

### Clipboard Entry
```http
POST /api/clipboard_entry
{
  "origin": "Linux@192.168.1.10",
  "platform": "Linux",
  "type": "text",
  "entry": "Hello world",
  "timestamp": "2026-05-28T12:00:00Z"
}
```

### File Request
```http
POST /api/file
{
  "path": "/absolute/path/to/shared-file.txt"
}
```
# Planned Features

- IPV6 support
- Image snippet support
- Configurable Peer List

---
## 📄 License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.
