# Code Walkthrough

This document is a guided tour of the LanClipboard codebase for contributors.

It focuses on:

- how the app starts
- how clipboard data moves through the system
- how discovery and peer authorization work
- how text and file transfer differ
- where security is applied
- where to look when debugging a specific behavior

## High-Level Shape

LanClipboard is a FastAPI application with a few long-running background threads:

- a clipboard polling thread
- a paste queue worker
- a keyboard listener thread on non-Wayland systems
- an async mDNS discovery service

The FastAPI app is mainly used for peer-to-peer exchange:

- `/api/handshake` authorizes peers
- `/api/clipboard_entry` receives clipboard updates
- `/api/file` streams shared files on demand

The main entrypoint is [main.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/main.py).

## Startup Flow

App startup happens in the FastAPI lifespan defined in [main.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/main.py).

At a high level it does this:

1. Load config from [config/config.yaml](/Users/cloudraccoon/PycharmProjects/LanClipBoard/config/config.yaml) via [config/config_loader.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/config/config_loader.py).
2. Resolve runtime identity:
   - local IP
   - local device id like `Darwin@192.168.100.64`
   - device name
3. Create shared state objects:
   - `ClipboardStorage`
   - `PeerRegistry`
   - `SharedFileRegistry`
   - `Queue` for paste requests
4. Load security keys from the configured archive if security is enabled.
5. Start discovery and optional bootstrap peer handshakes.
6. Start background workers:
   - clipboard monitor
   - paste queue handler
   - keyboard listener when supported

The FastAPI router itself is built in [api_module.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/api_module.py).

## Main Runtime Pieces

### `main.py`

This file wires the whole app together.

Key responsibilities:

- config loading
- logging setup
- key archive loading
- thread startup/shutdown
- app state initialization
- mDNS lifecycle startup

If you want to understand “what exists at runtime”, start here.

### `clipboard_factory.py`

This chooses the platform-specific clipboard backend:

- [mac_clipboard.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/mac_clipboard.py)
- [windows_clipboard.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/windows_clipboard.py)
- [linux_clipboard.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/linux_clipboard.py)

Each backend implements the interface expected by the rest of the app:

- read current clipboard contents
- write text or file lists
- trigger a native paste gesture after writing

### `clipboard_listener.py`

This is the outbound side of synchronization.

It polls the local clipboard and, when it detects a new value:

1. wraps it in a `ClipboardEntry`
2. stores it locally
3. registers file paths in `SharedFileRegistry` if the clipboard contains files
4. broadcasts the entry to authorized peers

Important detail:

- it uses fingerprinting and a short suppression window to avoid rebroadcasting clipboard changes that LanClipboard itself just wrote

### `clipboard_storage.py`

This is the local in-memory store for the latest clipboard entry per peer.

It does three useful things:

- validates incoming entries
- keeps only the latest entry for each address
- suppresses self-induced clipboard loops

On Wayland, remote clipboard entries can be pushed directly into the paste queue because a global keyboard hook is not available in the same way.

### `paste_queue_handler.py`

This is the inbound “apply the remote clipboard locally” worker.

It consumes `ClipboardEntry` objects from the queue and:

- pastes text directly
- downloads remote files via `/api/file` before pasting them locally
- skips HTTP for local file entries and pastes the local file paths directly

That last rule matters because clipboard entries created on the current device use the local device id as `origin`, not a plain IP.

### `keyboard_listener.py`

This listens for the configured paste hotkey and enqueues the latest available clipboard entry for local paste.

Important platform behavior:

- on Windows, it uses a low-level Win32 filter to suppress the physical hotkey and avoid native-app double paste
- the Win32 hook can also trigger the paste action directly when it detects the configured chord
- `combo_active` prevents duplicate triggers if both the hook and `pynput` observe the same chord

This file is the place to inspect when hotkey behavior is platform-specific.

### `mdns_discovery.py`

This handles:

- mDNS service registration
- mDNS browsing
- peer discovery callbacks
- bootstrap peer handshakes
- periodic re-announcement of the local service

Discovery is best-effort. The practical fallback is `network.bootstrap_peers`.

The discovery service only authorizes a peer after a successful handshake.

### `api_module.py`

This contains the FastAPI router and the peer-to-peer HTTP behavior.

The most important endpoints are:

- `POST /api/handshake`
- `POST /api/clipboard_entry`
- `POST /api/file`

It also contains helper functions for:

- encrypting/decrypting request bodies
- broadcasting clipboard updates to peers
- downloading files from a peer

This file is the best place to inspect when you are debugging network behavior.

### `peer_registry.py`

This is the thread-safe in-memory peer authorization registry.

It tracks:

- candidate IPs discovered via mDNS or bootstrap
- authorized peers by IP
- authorized peers by device id

Current trust is still mostly network-oriented:

- peers are allowed after handshake
- authorization is keyed primarily by IP at request time

### `shared_file_registry.py`

This is a TTL-based allowlist for file sharing.

When the local user copies files, those paths are registered temporarily. Later, if a peer requests one of those paths through `/api/file`, the request is allowed only if the file is still in the allowlist.

This keeps `/api/file` from being a general-purpose file reader.

### `security_services.py`

This is where all crypto helpers live.

It currently handles:

- RSA keypair generation
- encrypted zip key archives
- JWE encryption for JSON payloads
- Fernet-based file encryption
- RSA-wrapped file keys

For file transfers, the encrypted file format now includes the original filename so decrypting a temporary `.enc` file restores the correct basename and extension.

### `config_ui.py`

This is the Tkinter-based desktop configurator.

It is responsible for:

- editing `config.yaml`
- configuring security settings
- generating/importing key archives
- editing bootstrap peers and testing/debugging flags
- launching the app via `uvicorn`

If a user reports “the app works when started from the terminal but not the GUI”, this is the first file to inspect.

## Data Model

The main wire model is `ClipboardEntry` in [clipboard_storage.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/clipboard_storage.py).

It contains:

- `origin`
- `platform`
- `type`
- `entry`
- `timestamp`

`type` is currently one of:

- `text`
- `files`

File payloads are serialized as JSON arrays of paths by [clipboard_payloads.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/clipboard_payloads.py).

## Text Sync Flow

The text path is:

1. User copies text locally.
2. `clipboard_listener.monitor_clipboard()` detects a new clipboard value.
3. A `ClipboardEntry(type="text")` is created and stored.
4. `broadcast_to_peers()` in [api_module.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/api_module.py) POSTs it to each authorized peer.
5. The receiving peer accepts it at `POST /api/clipboard_entry`.
6. The entry is stored in `ClipboardStorage`.
7. When the user triggers the paste hotkey, `paste_queue_handler()` applies it locally.

## File Sync Flow

The file path is slightly different because file contents are not sent inside `ClipboardEntry`.

1. User copies one or more files locally.
2. The local clipboard backend returns `type="files"` and a JSON list of paths.
3. `clipboard_listener` stores the entry and registers the file paths in `SharedFileRegistry`.
4. The file-list entry is broadcast to peers.
5. The receiving side stores the file-list entry.
6. When the user triggers paste:
   - if the entry originated on a remote peer, the app calls `get_files()` and fetches each file via `POST /api/file`
   - if the entry originated locally, the app pastes the local file paths directly
7. The local clipboard backend writes the downloaded file paths to the native clipboard and performs a paste gesture.

Important consequence:

- file payloads are lazy-loaded on paste, not eagerly transferred on copy

## Security Model

Security is optional and currently payload-focused rather than transport-focused.

When enabled:

- clipboard and file request bodies can be JWE-encrypted
- file bytes are encrypted with a per-file Fernet key
- the Fernet key is encrypted with RSA

What is not fully hardened yet:

- transport is still plain HTTP rather than HTTPS
- handshake metadata can still be plaintext
- peers are still authorized through the peer registry rather than strong per-device identity pinning

For operational guidance, see [docs/SECURITY.md](/Users/cloudraccoon/PycharmProjects/LanClipBoard/docs/SECURITY.md).

## Discovery and Trust Flow

Discovery and trust are related but separate:

- mDNS discovers candidate peers
- bootstrap peers provide static candidates
- handshake decides whether a peer is accepted
- accepted peers are stored in `PeerRegistry`
- only authorized peers can call `/api/clipboard_entry` and `/api/file`

This means a peer can be reachable on the network but still blocked from exchanging clipboard data until handshake succeeds.

## Tests

The tests are small, focused regression checks rather than large end-to-end integration tests.

Useful files:

- [tests/test_api_module.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/tests/test_api_module.py)
- [tests/test_keyboard_listener.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/tests/test_keyboard_listener.py)
- [tests/test_peer_registry.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/tests/test_peer_registry.py)
- [tests/test_shared_file_registry.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/tests/test_shared_file_registry.py)
- [tests/test_clipboard_payloads.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/tests/test_clipboard_payloads.py)
- [tests/test_clipboard_storage.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/tests/test_clipboard_storage.py)
- [tests/test_paste_queue_handler.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/tests/test_paste_queue_handler.py)
- [tests/test_security_file_transfer.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/tests/test_security_file_transfer.py)

If you are adding a bug fix, try to add a focused regression test next to the module you changed.

## Common Debugging Paths

If this breaks, start here:

- App does not start:
  - [main.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/main.py)
  - [config/config_loader.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/config/config_loader.py)
- Discovery fails:
  - [mdns_discovery.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/mdns_discovery.py)
  - [peer_registry.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/peer_registry.py)
- Remote text does not paste:
  - [keyboard_listener.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/keyboard_listener.py)
  - [paste_queue_handler.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/paste_queue_handler.py)
- File transfer fails:
  - [api_module.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/api_module.py)
  - [shared_file_registry.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/shared_file_registry.py)
  - [security_services.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/security_services.py)
- GUI config behaves differently:
  - [config_ui.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/config_ui.py)

## Suggested Reading Order

If you are new to the project, this order works well:

1. [README.md](/Users/cloudraccoon/PycharmProjects/LanClipBoard/README.md)
2. [main.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/main.py)
3. [api_module.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/api_module.py)
4. [clipboard_listener.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/clipboard_listener.py)
5. [paste_queue_handler.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/paste_queue_handler.py)
6. [mdns_discovery.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/mdns_discovery.py)
7. platform clipboard backend for your OS
8. [security_services.py](/Users/cloudraccoon/PycharmProjects/LanClipBoard/security_services.py)

That gives you the runtime flow first, then the platform-specific details.
