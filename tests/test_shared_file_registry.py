"""Tests for the shared file allowlist."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
from pathlib import Path

from shared_file_registry import SharedFileRegistry


def test_registered_path_is_allowed(tmp_path: Path):
    file_path = tmp_path / "shared.txt"
    file_path.write_text("hello", encoding="utf-8")

    registry = SharedFileRegistry()
    registry.register_paths([str(file_path)])

    assert registry.is_allowed(file_path) is True
