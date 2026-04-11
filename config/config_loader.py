"""YAML-backed typed configuration for the LanClipBoard service."""

import platform
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


def default_paste_hotkey() -> list[str]:
    if platform.system() == "Darwin":
        return ["Key.cmd", "Key.shift", "v"]
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
    """Peer policy flags (``auto_accept`` is reserved for future enforcement; not yet read by the server)."""

    auto_accept: bool


class AppConfig(BaseModel):
    """Root configuration object produced by :func:`load_config`."""

    device: DeviceConfig
    network: NetworkConfig
    hotkeys: HotkeyConfig
    clipboard: ClipboardConfig
    security: SecurityConfig
    peers: PeerConfig


def load_config(path: str = "config/config.yaml") -> AppConfig:
    """Load and validate ``config.yaml`` (or *path*) into an :class:`AppConfig`."""
    config_path = Path(path)

    if not config_path.exists():
        raise RuntimeError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return AppConfig(**raw)