"""Tests for key archive extraction safety."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import tempfile
from pathlib import Path

import pyzipper
import pytest

import security_services


def test_unpack_keys_rejects_zip_slip(tmp_path: Path):
    archive = tmp_path / "keys.zip"
    dest = tmp_path / "out"
    dest.mkdir()

    with pyzipper.AESZipFile(archive, "w", compression=pyzipper.ZIP_DEFLATED) as zf:
        zf.writestr("../../../evil.pem", b"not-a-real-key")

    with pytest.raises(ValueError, match="Unsafe|Archive entry"):
        security_services.unpack_keys(archive_path=archive, destination_dir=dest)


def test_unpack_keys_extracts_safe_member(tmp_path: Path):
    archive = tmp_path / "keys.zip"
    dest = tmp_path / "out"
    dest.mkdir()
    content = b"-----BEGIN PUBLIC KEY-----\nabc\n-----END PUBLIC KEY-----\n"

    with pyzipper.AESZipFile(archive, "w", compression=pyzipper.ZIP_DEFLATED) as zf:
        zf.writestr("device_public.pem", content)

    files = security_services.unpack_keys(archive_path=archive, destination_dir=dest)
    assert len(files) == 1
    assert files[0].read_bytes() == content
