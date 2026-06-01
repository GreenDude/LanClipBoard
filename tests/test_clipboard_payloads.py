"""Tests for JSON-based file clipboard payload helpers."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import pytest

from clipboard_payloads import parse_file_list, serialize_file_list


def test_serialize_and_parse_file_list_round_trip():
    payload = serialize_file_list(["/tmp/a.txt", "/tmp/b.txt"])
    assert parse_file_list(payload) == ["/tmp/a.txt", "/tmp/b.txt"]


def test_parse_file_list_rejects_non_list_payload():
    with pytest.raises(ValueError):
        parse_file_list('{"path":"/tmp/a.txt"}')
