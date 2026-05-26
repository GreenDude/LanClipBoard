"""Track clipboard-shared local files that remote peers may request."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
from __future__ import annotations

import time
from pathlib import Path
from threading import RLock


class SharedFileRegistry:
    """Small TTL-based allowlist for outbound file transfers."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self._lock = RLock()
        self._allowed_paths: dict[Path, float] = {}

    def register_paths(self, paths: list[str]) -> None:
        expires_at = time.time() + self.ttl_seconds
        with self._lock:
            self._prune_locked()
            for path in paths:
                resolved = Path(path).expanduser().resolve(strict=False)
                self._allowed_paths[resolved] = expires_at

    def is_allowed(self, path: Path) -> bool:
        resolved = path.expanduser().resolve(strict=False)
        with self._lock:
            self._prune_locked()
            expires_at = self._allowed_paths.get(resolved)
            return expires_at is not None and expires_at >= time.time()

    def _prune_locked(self) -> None:
        now = time.time()
        expired = [path for path, expires_at in self._allowed_paths.items() if expires_at < now]
        for path in expired:
            self._allowed_paths.pop(path, None)
