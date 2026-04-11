"""Tests for API helpers and request models."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import unquote

import pytest
from pydantic import ValidationError

import api_module


def test_file_request_rejects_parent_path_segments():
    with pytest.raises(ValidationError):
        api_module.FileRequest(path="/tmp/../etc/passwd")


def test_parse_handshake_body_accepts_plain_json_without_using_private_key():
    body = json.dumps(
        {
            "device_id": "Linux@192.168.1.2",
            "device_name": "dev",
            "platform": "Linux",
            "protocol_version": 1,
            "supports_text": True,
            "supports_files": True,
            "supports_encryption": False,
        }
    ).encode("utf-8")
    request = MagicMock()
    request.app = SimpleNamespace(
        state=SimpleNamespace(private_key_pem=b"would-break-if-used-wrongly", private_key_password=None)
    )
    text = api_module._parse_handshake_body(request, body)
    parsed = json.loads(text)
    assert parsed["device_id"] == "Linux@192.168.1.2"


def test_attachment_content_disposition_preserves_spaces():
    header = api_module._attachment_content_disposition("Test File 1.txt")
    assert "Test File 1.txt" in header
    assert "%20" not in header


def test_unquote_restores_filename_from_legacy_percent_encoding():
    assert unquote("Test%20File%201.txt") == "Test File 1.txt"
