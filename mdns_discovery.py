"""mDNS registration and peer discovery for LanClipBoard."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import asyncio
import logging
import socket
import threading
import time
from typing import Optional

import httpx
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf
from peer_registry import PeerRegistry

logger = logging.getLogger(__name__)


class LanClipboardDiscovery:
    """Register ``_lanclipboard._tcp`` services, browse peers, and perform HTTP handshakes."""

    SERVICE_TYPE = "_lanclipboard._tcp.local."
    BROWSER_DELAY_MS = 1_000
    ANNOUNCE_INTERVAL_SECONDS = 15

    def __init__(
        self,
        local_id: str,
        local_ip: str,
        device_name: str,
        platform_name: str,
        port: int,
        protocol_version: int = 1,
        peer_registry: PeerRegistry | None = None,
        peer_public_key_pem: bytes | None = None,
    ):
        """Capture local identity, listen address, shared *peer_list*, and optional local public PEM."""
        self.local_id = local_id
        self.local_ip = local_ip
        self.device_name = device_name
        self.platform_name = platform_name
        self.port = port
        self.protocol_version = protocol_version
        self.peer_registry = peer_registry if peer_registry is not None else PeerRegistry()
        # Local public PEM (if any); advertised in TXT. Not used to encrypt outbound handshake
        # without the remote peer's public key (that would produce ciphertext the peer cannot open).
        self.peer_public_key_pem = peer_public_key_pem

        self.aiozc: Optional[AsyncZeroconf] = None
        self.browser: AsyncServiceBrowser | None = None
        self.service_info = None
        self._seen = {}
        self._service_ips: dict[str, str] = {}
        self._remote_service_seen = False
        self._discovery_hint_task: asyncio.Task | None = None
        self._announce_task: asyncio.Task | None = None
        self._announce_seq = 0
        self._stopped = False
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self):
        """Bind Zeroconf to *local_ip*, publish this service, and subscribe to peer updates."""
        from zeroconf import IPVersion, InterfaceChoice, ServiceInfo

        safe_device_name = self.device_name.removesuffix(".local")
        service_name = f"{safe_device_name}.{self.SERVICE_TYPE}"

        properties = {
            b"device_id": self.local_id.encode("utf-8"),
            b"device_name": safe_device_name.encode("utf-8"),
            b"platform": self.platform_name.encode("utf-8"),
            b"protocol_version": str(self.protocol_version).encode("utf-8"),
            b"announce_seq": b"0",
        }

        self.aiozc = AsyncZeroconf(
            interfaces=InterfaceChoice.All,
            ip_version=IPVersion.V4Only,
        )
        logger.info(
            "[discovery] start "
            "local_id=%s local_ip=%s device_name=%s port=%s auto_accept=%s "
            "zeroconf_interfaces=All zeroconf_ip_version=V4Only",
            self.local_id,
            self.local_ip,
            safe_device_name,
            self.port,
            self.peer_registry.auto_accept,
        )

        self.service_info = ServiceInfo(
            type_=self.SERVICE_TYPE,
            name=service_name,
            addresses=[socket.inet_aton(self.local_ip)],
            port=self.port,
            properties=properties,
            server=f"{safe_device_name}.local.",
        )

        self._loop = asyncio.get_running_loop()
        self.browser = AsyncServiceBrowser(
            self.aiozc.zeroconf,
            self.SERVICE_TYPE,
            listener=self,
            delay=self.BROWSER_DELAY_MS,
        )
        logger.info(
            "[discovery] browser started service_type=%s delay_ms=%s thread=%s",
            self.SERVICE_TYPE,
            self.BROWSER_DELAY_MS,
            threading.current_thread().name,
        )

        await self.aiozc.async_register_service(self.service_info)
        logger.info(
            "[discovery] registered %s at %s:%s props=%s",
            service_name,
            self.local_ip,
            self.port,
            properties,
        )
        self._discovery_hint_task = asyncio.create_task(self._log_discovery_hint())
        self._announce_task = asyncio.create_task(self._periodic_announce())

    async def bootstrap_handshake(self, peers: list[str] | None):
        """Shake hands with statically configured *peers* (IPs), skipping self and empty entries."""
        if not peers:
            logger.info("[discovery] bootstrap skipped: no peers configured")
            return

        for ip in peers:
            if not ip or ip == self.local_ip:
                continue

            self.peer_registry.mark_candidate(ip)
            logger.info(
                "[discovery] bootstrap handshake with %s:%s registry=%s",
                ip,
                self.port,
                self.peer_registry.debug_snapshot(),
            )
            await self._handshake_with_peer(ip, self.port)

    async def stop(self):
        """Stop browsing and unregister Zeroconf resources."""
        self._stopped = True
        if self._discovery_hint_task is not None:
            self._discovery_hint_task.cancel()
            self._discovery_hint_task = None
        if self._announce_task is not None:
            self._announce_task.cancel()
            self._announce_task = None
        if self.browser is not None:
            await self.browser.async_cancel()
            self.browser = None
        if self.aiozc is not None:
            await self.aiozc.async_close()
        logger.info("[discovery] stopped")

    # ---- ServiceListener-style callbacks used by async_add_service_listener ----

    def _schedule_service_update(self, service_type: str, name: str) -> None:
        """Run :meth:`handle_service_update` on the asyncio loop from a Zeroconf thread."""
        if self._loop is None or self._stopped:
            logger.info(
                "[discovery] skipped scheduling update name=%s stopped=%s loop_ready=%s",
                name,
                self._stopped,
                self._loop is not None,
            )
            return
        try:
            logger.info(
                "[discovery] scheduling service update name=%s type=%s from_thread=%s",
                name,
                service_type,
                threading.current_thread().name,
            )
            asyncio.run_coroutine_threadsafe(
                self.handle_service_update(service_type, name),
                self._loop,
            )
        except RuntimeError:
            logger.exception("[discovery] failed to schedule service update")

    def add_service(self, zc, service_type: str, name: str) -> None:
        """Zeroconf callback when a new instance appears."""
        logger.info("[discovery] add_service: %s", name)
        self._schedule_service_update(service_type, name)

    def update_service(self, zc, service_type: str, name: str) -> None:
        """Zeroconf callback when TXT or addresses change."""
        logger.info("[discovery] update_service: %s", name)
        self._schedule_service_update(service_type, name)

    def remove_service(self, zc, service_type: str, name: str) -> None:
        """Zeroconf callback when a service goes away."""
        logger.info("[discovery] remove_service: %s", name)
        ip = self._service_ips.pop(name, None)
        if ip is not None:
            self.peer_registry.revoke_ip(ip)
            logger.info(
                "[discovery] revoked peer ip=%s registry=%s",
                ip,
                self.peer_registry.debug_snapshot(),
            )

    async def handle_service_update(self, service_type: str, name: str):
        """Resolve a service, rate-limit by *device_id*, and invoke :meth:`_handshake_with_peer`."""
        if self._stopped or self.aiozc is None:
            return

        logger.info(
            "[discovery] service update: %s registry_before=%s",
            name,
            self.peer_registry.debug_snapshot(),
        )

        info = AsyncServiceInfo(service_type, name)
        ok = await info.async_request(self.aiozc.zeroconf, timeout=3000)
        if not ok:
            logger.info("[discovery] no service info for %s", name)
            return

        props = {
            (k.decode("utf-8") if isinstance(k, bytes) else k):
            (v.decode("utf-8") if isinstance(v, bytes) else v)
            for k, v in info.properties.items()
        }

        logger.info("[discovery] resolved props for %s: %s", name, props)

        remote_id = props.get("device_id")
        if not remote_id:
            logger.info("[discovery] ignoring %s: no device_id", name)
            return

        if remote_id == self.local_id:
            logger.info("[discovery] ignoring self: %s", remote_id)
            return
        self._remote_service_seen = True

        addresses = info.parsed_addresses()
        # TODO: Add IPV6 support
        ipv4_addresses = [a for a in addresses if "." in a]

        if not ipv4_addresses:
            logger.info("[discovery] no IPv4 address for %s, skipping", name)
            return

        ip = ipv4_addresses[0]
        port = info.port
        self._service_ips[name] = ip
        self.peer_registry.mark_candidate(ip)

        logger.info("[discovery] all addresses: %s", addresses)
        logger.info("[discovery] selected IPv4: %s", ip)

        now = time.time()
        last_seen = self._seen.get(remote_id, 0)
        if now - last_seen < 5:
            logger.info(
                "[discovery] rate-limited peer remote_id=%s ip=%s last_seen_delta=%.2fs",
                remote_id,
                ip,
                now - last_seen,
            )
            return
        self._seen[remote_id] = now

        logger.info(
            "[discovery] found peer %s at %s:%s registry_after_candidate=%s",
            remote_id,
            ip,
            port,
            self.peer_registry.debug_snapshot(),
        )
        await self._handshake_with_peer(ip, port)

    async def _log_discovery_hint(self) -> None:
        """Emit a one-shot hint when mDNS does not reveal any remote peers after startup."""
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            return

        if self._stopped:
            return

        if self._remote_service_seen:
            return

        if self.peer_registry.get_authorized_ips():
            return

        logger.warning(
            "[discovery] no remote mDNS services detected after startup. "
            "Discovery may be blocked by the local network, firewall, Avahi/Bonjour, or multicast filtering. "
            "Set network.bootstrap_peers in config/config.yaml for a reliable cross-platform fallback."
        )

    async def _periodic_announce(self) -> None:
        """Periodically re-announce the local service so late-starting peers can detect it."""
        try:
            while not self._stopped and self.aiozc is not None and self.service_info is not None:
                await asyncio.sleep(self.ANNOUNCE_INTERVAL_SECONDS)
                if self._stopped or self.aiozc is None or self.service_info is None:
                    return

                self._announce_seq += 1
                self.service_info.properties[b"announce_seq"] = str(self._announce_seq).encode("utf-8")
                await self.aiozc.async_update_service(self.service_info)
                logger.info(
                    "[discovery] re-announced local service announce_seq=%s interval_seconds=%s",
                    self._announce_seq,
                    self.ANNOUNCE_INTERVAL_SECONDS,
                )
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("[discovery] periodic re-announce failed")

    async def _handshake_with_peer(self, ip: str, port: int):
        """POST plaintext JSON to the peer's handshake endpoint and maybe append *ip* to *peer_list*."""
        url = f"http://{ip}:{port}/api/handshake"

        payload = {
            "device_id": self.local_id,
            "device_name": self.device_name,
            "platform": self.platform_name,
            "protocol_version": self.protocol_version,
            "supports_text": True,
            "supports_files": True,
            "supports_encryption": self.peer_public_key_pem is not None,
        }

        data = None
        async with httpx.AsyncClient(timeout=3.0) as client:
            for attempt in range(1, 4):
                try:
                    logger.info(
                        "[discovery] attempting handshake with peer %s:%s (attempt %s)",
                        ip,
                        port,
                        attempt,
                    )
                    logger.debug("[discovery] sending handshake to peer %s:%s payload=%s", ip, port, payload)
                    r = await client.post(url, json=payload)

                    r.raise_for_status()
                    data = r.json()
                    logger.info("[discovery] handshake with peer %s:%s result: %s", ip, port, data)
                except Exception:
                    logger.exception("[discovery] handshake failed with %s:%s", ip, port)
                    if attempt < 3:
                        await asyncio.sleep(1.0)
                    continue

                if data.get("accepted"):
                    break
                if data.get("reason") == "peer_not_allowed" and attempt < 3:
                    await asyncio.sleep(1.0)
                    continue
                break

        if data is None:
            return

        if not data.get("accepted"):
            logger.warning("[discovery] handshake rejected by %s:%s: %s", ip, port, data.get("reason"))
            return

        self.peer_registry.authorize(
            ip=ip,
            device_id=data.get("device_id", ""),
            device_name=data.get("device_name", ""),
            platform=data.get("platform", ""),
            port=port,
        )
        logger.info(
            "[discovery] added peer %s to peer registry registry=%s",
            ip,
            self.peer_registry.debug_snapshot(),
        )

        logger.info(
            "[discovery] handshake accepted by %s (%s) at %s:%s",
            data.get("device_name"),
            data.get("device_id"),
            ip,
            port,
        )
