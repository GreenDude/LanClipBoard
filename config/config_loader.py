import yaml
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List


class DeviceConfig(BaseModel):
    id: str
    name: str


class NetworkConfig(BaseModel):
    port: int
    discovery: bool
    bootstrap_peers: list[str] = []


class HotkeyConfig(BaseModel):
    paste: List[str]


class ClipboardConfig(BaseModel):
    poll_interval_ms: int


class SecurityConfig(BaseModel):
    enabled: bool
    key_archive: Optional[str]
    key_password: Optional[str]


class PeerConfig(BaseModel):
    auto_accept: bool


class AppConfig(BaseModel):
    device: DeviceConfig
    network: NetworkConfig
    hotkeys: HotkeyConfig
    clipboard: ClipboardConfig
    security: SecurityConfig
    peers: PeerConfig


def load_config(path: str = "config/config.yaml") -> AppConfig:
    config_path = Path(path)

    if not config_path.exists():
        raise RuntimeError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return AppConfig(**raw)