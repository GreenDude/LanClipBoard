"""Thread-safe peer authorization registry."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(slots=True)
class PeerRecord:
    """Metadata tracked for an accepted peer."""

    ip: str
    device_id: str
    device_name: str
    platform: str
    port: int | None = None


class PeerRegistry:
    """Track discovered candidates and authorized peers across threads."""

    def __init__(self, auto_accept: bool = True) -> None:
        self.auto_accept = auto_accept
        self._lock = RLock()
        self._candidates: set[str] = set()
        self._authorized_by_ip: dict[str, PeerRecord] = {}
        self._authorized_by_device_id: dict[str, PeerRecord] = {}

    def mark_candidate(self, ip: str) -> None:
        with self._lock:
            self._candidates.add(ip)

    def can_accept(self, ip: str) -> bool:
        with self._lock:
            return self.auto_accept or ip in self._candidates

    def authorize(
        self,
        ip: str,
        device_id: str,
        device_name: str,
        platform: str,
        port: int | None = None,
    ) -> None:
        with self._lock:
            record = PeerRecord(
                ip=ip,
                device_id=device_id,
                device_name=device_name,
                platform=platform,
                port=port,
            )
            self._authorized_by_ip[ip] = record
            self._authorized_by_device_id[device_id] = record
            self._candidates.add(ip)

    def is_authorized(self, ip: str) -> bool:
        with self._lock:
            return ip in self._authorized_by_ip

    def revoke_ip(self, ip: str) -> None:
        with self._lock:
            record = self._authorized_by_ip.pop(ip, None)
            self._candidates.discard(ip)
            if record is not None:
                current = self._authorized_by_device_id.get(record.device_id)
                if current is not None and current.ip == ip:
                    self._authorized_by_device_id.pop(record.device_id, None)

    def get_authorized_ips(self) -> list[str]:
        with self._lock:
            return list(self._authorized_by_ip.keys())
