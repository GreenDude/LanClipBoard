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

```bash
git clone <repo>
cd lanclipboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## ▶️ Usage

```bash
python config_ui.py
python main.py
```

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
  "type": "text",
  "content": "Hello world"
}
```

### File Request
```http
POST /api/file
{
  "path": "/tmp/file.txt"
}
```
# Planned Features

- IPV6 support
- Image snippet support
- Configurable Peer List

---
## 📄 License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.