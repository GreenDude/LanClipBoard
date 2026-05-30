"""YAML-backed typed configuration for the LanClipBoard service."""

import copy
import platform
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


def default_paste_hotkey() -> list[str]:
    if platform.system() == "Darwin":
        return ["Key.cmd", "Key.shift", "v"]
    if platform.system() == "Windows":
        return ["Key.ctrl", "Key.shift", "Key.insert"]
    return ["Key.ctrl", "Key.shift", "v"]


class DeviceConfig(BaseModel):
    """Static device identity fields from YAML (``auto`` triggers runtime defaults)."""

    id: str
    name: str


class NetworkConfig(BaseModel):
    """HTTP port, mDNS toggle, and optional static peer IPs for bootstrap handshakes."""

    port: int
    discovery: bool
    bootstrap_peers: list[str] = Field(default_factory=list)


class HotkeyConfig(BaseModel):
    """Keyboard shortcuts interpreted by :mod:`keyboard_listener`."""

    paste: list[str] = Field(default_factory=default_paste_hotkey)


class ClipboardConfig(BaseModel):
    """Local clipboard polling interval for :func:`clipboard_listener.monitor_clipboard`."""

    poll_interval_ms: int


class SecurityConfig(BaseModel):
    """Optional encrypted key archive used for JWE clipboard/file payloads."""

    enabled: bool
    key_archive: Optional[str]
    key_password: Optional[str]


class PeerConfig(BaseModel):
    """Peer policy flags controlling whether unknown peers may auto-authorize."""

    auto_accept: bool


class TestingConfig(BaseModel):
    """Configuration used for testing."""
    endpoints_enabled: bool = False
    log_key_input: bool = False


class AppConfig(BaseModel):
    """Root configuration object produced by :func:`load_config`."""

    device: DeviceConfig
    network: NetworkConfig
    hotkeys: HotkeyConfig
    clipboard: ClipboardConfig
    security: SecurityConfig
    peers: PeerConfig
    testing: TestingConfig = Field(default_factory=TestingConfig)


DEFAULT_CONFIG_DICT = {
    "device": {
        "id": "auto",
        "name": "auto",
    },
    "network": {
        "port": 8000,
        "discovery": True,
        "bootstrap_peers": [],
    },
    "hotkeys": {
        "paste": default_paste_hotkey(),
    },
    "clipboard": {
        "poll_interval_ms": 200,
    },
    "security": {
        "enabled": False,
        "key_archive": None,
        "key_password": None,
    },
    "peers": {
        "auto_accept": True,
    },
    "testing": {
        "endpoints_enabled": False,
        "log_key_input": False,
    },
}


def _merge_config_defaults(raw: dict | None) -> dict:
    """Merge *raw* config with known defaults so older config files still load."""
    merged = copy.deepcopy(DEFAULT_CONFIG_DICT)
    if not isinstance(raw, dict):
        return merged

    for section, default_values in merged.items():
        incoming = raw.get(section)
        if isinstance(default_values, dict) and isinstance(incoming, dict):
            default_values.update(incoming)
        elif incoming is not None:
            merged[section] = incoming
    return merged


def load_config(path: str = "config/config.yaml") -> AppConfig:
    """Load and validate ``config.yaml`` (or *path*) into an :class:`AppConfig`."""
    config_path = Path(path)

    if not config_path.exists():
        raise RuntimeError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return AppConfig(**_merge_config_defaults(raw))
