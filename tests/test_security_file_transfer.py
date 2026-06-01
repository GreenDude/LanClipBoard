"""Tests for encrypted file transfer helpers."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
from pathlib import Path

import security_services


def test_encrypt_decrypt_file_preserves_original_filename(tmp_path: Path):
    private_key, public_key = security_services.generate_key_pair()
    source = tmp_path / "New Text Document.txt"
    source.write_text("hello", encoding="utf-8")

    encrypted_path = security_services.encrypt_file(public_key, source, output_dir=tmp_path)
    assert encrypted_path is not None
    assert encrypted_path.endswith(".enc")

    decrypted_path = security_services.decrypt_file(private_key, None, encrypted_path, output_dir=tmp_path)
    assert decrypted_path is not None
    assert Path(decrypted_path).name == "New Text Document.txt"
    assert Path(decrypted_path).read_text(encoding="utf-8") == "hello"
