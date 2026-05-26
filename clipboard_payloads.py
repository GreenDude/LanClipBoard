"""Helpers for serializing and validating clipboard payloads."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
from __future__ import annotations

import json
from pathlib import Path


def serialize_file_list(paths: list[str]) -> str:
    """Encode *paths* as compact JSON for wire transfer."""
    normalized = [str(Path(path)) for path in paths if path]
    return json.dumps(normalized, separators=(",", ":"))


def parse_file_list(payload: str) -> list[str]:
    """Decode a JSON list of file paths from *payload*."""
    decoded = json.loads(payload)
    if not isinstance(decoded, list) or any(not isinstance(item, str) or not item for item in decoded):
        raise ValueError("file payload must be a non-empty JSON array of paths")
    return decoded
