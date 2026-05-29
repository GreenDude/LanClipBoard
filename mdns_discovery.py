"""mDNS registration and peer discovery for LanClipBoard."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
import asyncio
import socket
import threading
import time
from typing import Optional

import httpx
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf
from peer_registry import PeerRegistry


class LanClipboardDiscovery:
    """Register ``_lanclipboard._tcp`` services, browse peers, and perform HTTP handshakes."""

    SERVICE_TYPE = "_lanclipboard._tcp.local."
    BROWSER_DELAY_MS = 1_000

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
        }

        self.aiozc = AsyncZeroconf(
            interfaces=InterfaceChoice.All,
            ip_version=IPVersion.V4Only,
        )
        print(
            "[discovery] start "
            f"local_id={self.local_id} local_ip={self.local_ip} device_name={safe_device_name} "
            f"port={self.port} auto_accept={self.peer_registry.auto_accept} "
            "zeroconf_interfaces=All zeroconf_ip_version=V4Only"
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
        print(
            f"[discovery] browser started service_type={self.SERVICE_TYPE} delay_ms={self.BROWSER_DELAY_MS} "
            f"thread={threading.current_thread().name}"
        )

        await self.aiozc.async_register_service(self.service_info)
        print(
            f"[discovery] registered {service_name} at {self.local_ip}:{self.port} "
            f"props={properties}"
        )
        self._discovery_hint_task = asyncio.create_task(self._log_discovery_hint())

    async def bootstrap_handshake(self, peers: list[str] | None):
        """Shake hands with statically configured *peers* (IPs), skipping self and empty entries."""
        if not peers:
            print("[discovery] bootstrap skipped: no peers configured")
            return

        for ip in peers:
            if not ip or ip == self.local_ip:
                continue

            self.peer_registry.mark_candidate(ip)
            print(
                f"[discovery] bootstrap handshake with {ip}:{self.port} "
                f"registry={self.peer_registry.debug_snapshot()}"
            )
            await self._handshake_with_peer(ip, self.port)

    async def stop(self):
        """Stop browsing and unregister Zeroconf resources."""
        self._stopped = True
        if self._discovery_hint_task is not None:
            self._discovery_hint_task.cancel()
            self._discovery_hint_task = None
        if self.browser is not None:
            await self.browser.async_cancel()
            self.browser = None
        if self.aiozc is not None:
            await self.aiozc.async_close()
        print("[discovery] stopped")

    # ---- ServiceListener-style callbacks used by async_add_service_listener ----

    def _schedule_service_update(self, service_type: str, name: str) -> None:
        """Run :meth:`handle_service_update` on the asyncio loop from a Zeroconf thread."""
        if self._loop is None or self._stopped:
            print(
                f"[discovery] skipped scheduling update name={name} stopped={self._stopped} "
                f"loop_ready={self._loop is not None}"
            )
            return
        try:
            print(
                f"[discovery] scheduling service update name={name} type={service_type} "
                f"from_thread={threading.current_thread().name}"
            )
            asyncio.run_coroutine_threadsafe(
                self.handle_service_update(service_type, name),
                self._loop,
            )
        except RuntimeError as e:
            print(f"[discovery] failed to schedule service update: {e}")

    def add_service(self, zc, service_type: str, name: str) -> None:
        """Zeroconf callback when a new instance appears."""
        print(f"[discovery] add_service: {name}")
        self._schedule_service_update(service_type, name)

    def update_service(self, zc, service_type: str, name: str) -> None:
        """Zeroconf callback when TXT or addresses change."""
        print(f"[discovery] update_service: {name}")
        self._schedule_service_update(service_type, name)

    def remove_service(self, zc, service_type: str, name: str) -> None:
        """Zeroconf callback when a service goes away."""
        print(f"[discovery] remove_service: {name}")
        ip = self._service_ips.pop(name, None)
        if ip is not None:
            self.peer_registry.revoke_ip(ip)
            print(f"[discovery] revoked peer ip={ip} registry={self.peer_registry.debug_snapshot()}")

    async def handle_service_update(self, service_type: str, name: str):
        """Resolve a service, rate-limit by *device_id*, and invoke :meth:`_handshake_with_peer`."""
        if self._stopped or self.aiozc is None:
            return

        print(
            f"[discovery] service update: {name} "
            f"registry_before={self.peer_registry.debug_snapshot()}"
        )

        info = AsyncServiceInfo(service_type, name)
        ok = await info.async_request(self.aiozc.zeroconf, timeout=3000)
        if not ok:
            print(f"[discovery] no service info for {name}")
            return

        props = {
            (k.decode("utf-8") if isinstance(k, bytes) else k):
            (v.decode("utf-8") if isinstance(v, bytes) else v)
            for k, v in info.properties.items()
        }

        print(f"[discovery] resolved props for {name}: {props}")

        remote_id = props.get("device_id")
        if not remote_id:
            print(f"[discovery] ignoring {name}: no device_id")
            return

        if remote_id == self.local_id:
            print(f"[discovery] ignoring self: {remote_id}")
            return
        self._remote_service_seen = True

        addresses = info.parsed_addresses()
        # TODO: Add IPV6 support
        ipv4_addresses = [a for a in addresses if "." in a]

        if not ipv4_addresses:
            print(f"[discovery] no IPv4 address for {name}, skipping")
            return

        ip = ipv4_addresses[0]
        port = info.port
        self._service_ips[name] = ip
        self.peer_registry.mark_candidate(ip)

        print(f"[discovery] all addresses: {addresses}")
        print(f"[discovery] selected IPv4: {ip}")

        now = time.time()
        last_seen = self._seen.get(remote_id, 0)
        if now - last_seen < 5:
            print(
                f"[discovery] rate-limited peer remote_id={remote_id} ip={ip} "
                f"last_seen_delta={now - last_seen:.2f}s"
            )
            return
        self._seen[remote_id] = now

        print(
            f"[discovery] found peer {remote_id} at {ip}:{port} "
            f"registry_after_candidate={self.peer_registry.debug_snapshot()}"
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

        print(
            "[discovery] no remote mDNS services detected after startup. "
            "Discovery may be blocked by the local network, firewall, Avahi/Bonjour, or multicast filtering. "
            "Set network.bootstrap_peers in config/config.yaml for a reliable cross-platform fallback."
        )

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
                    print(f"[discovery] attempting handshake with peer {ip}:{port} (attempt {attempt})")
                    print(f"[discovery] sending handshake to peer {ip}:{port}, \n\t{payload}")
                    r = await client.post(url, json=payload)

                    r.raise_for_status()
                    data = r.json()
                    print(f"[discovery] handshake with peer {ip}:{port} result: {data}")
                except Exception as e:
                    print(f"[discovery] handshake failed with {ip}:{port}: {e}")
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
            print(f"[discovery] handshake rejected by {ip}:{port}: {data.get('reason')}")
            return

        self.peer_registry.authorize(
            ip=ip,
            device_id=data.get("device_id", ""),
            device_name=data.get("device_name", ""),
            platform=data.get("platform", ""),
            port=port,
        )
        print(f"[discovery] added peer {ip} to peer registry registry={self.peer_registry.debug_snapshot()}")

        print(
            f"[discovery] handshake accepted by "
            f"{data.get('device_name')} ({data.get('device_id')}) at {ip}:{port}"
        )
