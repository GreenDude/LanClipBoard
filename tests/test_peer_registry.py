"""Tests for peer authorization behavior."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
from peer_registry import PeerRegistry


def test_manual_approval_required_when_auto_accept_disabled():
    registry = PeerRegistry(auto_accept=False)
    assert registry.can_accept("10.0.0.2") is False

    registry.mark_candidate("10.0.0.2")
    assert registry.can_accept("10.0.0.2") is True


def test_revoke_ip_removes_authorization():
    registry = PeerRegistry()
    registry.authorize("10.0.0.2", "peer-1", "Laptop", "Linux")
    assert registry.is_authorized("10.0.0.2") is True

    registry.revoke_ip("10.0.0.2")
    assert registry.is_authorized("10.0.0.2") is False
