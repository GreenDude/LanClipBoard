import socket
import time
from typing import Optional

import httpx
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

import security_services


class LanClipboardDiscovery:
    SERVICE_TYPE = "_lanclipboard._tcp.local."

    def __init__(
        self,
        local_id: str,
        local_ip: str,
        device_name: str,
        platform_name: str,
        port: int,
        protocol_version: int = 1,
        peer_list=None,
        peer_public_key_pem: bytes | None = None,
    ):
        self.local_id = local_id
        self.local_ip = local_ip
        self.device_name = device_name
        self.platform_name = platform_name
        self.port = port
        self.protocol_version = protocol_version
        self.peer_list = peer_list if peer_list is not None else []
        self.peer_public_key_pem = peer_public_key_pem

        self.aiozc: Optional[AsyncZeroconf] = None
        self.service_info = None
        self._seen = {}
        self._stopped = False

    async def start(self):
        from zeroconf import IPVersion, ServiceInfo

        safe_device_name = self.device_name.removesuffix(".local")
        service_name = f"{safe_device_name}.{self.SERVICE_TYPE}"

        properties = {
            b"device_id": self.local_id.encode("utf-8"),
            b"device_name": safe_device_name.encode("utf-8"),
            b"platform": self.platform_name.encode("utf-8"),
            b"protocol_version": str(self.protocol_version).encode("utf-8"),
        }

        self.aiozc = AsyncZeroconf(
            interfaces=[self.local_ip],
            ip_version=IPVersion.V4Only,
        )

        self.aiozc = AsyncZeroconf(
            ip_version=IPVersion.All,
        )

        self.service_info = ServiceInfo(
            type_=self.SERVICE_TYPE,
            name=service_name,
            addresses=[socket.inet_aton(self.local_ip)],
            port=self.port,
            properties=properties,
            server=f"{safe_device_name}.local.",
        )

        await self.aiozc.async_register_service(self.service_info)
        print(f"[discovery] registered {service_name} at {self.local_ip}:{self.port}")

        await self.aiozc.async_add_service_listener(self.SERVICE_TYPE, self)
        print("[discovery] browser started")

    async def bootstrap_handshake(self, peers: list[str]):
        for ip in peers:
            if not ip or ip == self.local_ip:
                continue

            print(f"[discovery] bootstrap handshake with {ip}:{self.port}")
            await self._handshake_with_peer(ip, self.port)

    async def stop(self):
        self._stopped = True
        if self.aiozc is not None:
            await self.aiozc.async_close()
        print("[discovery] stopped")

    # ---- ServiceListener-style callbacks used by async_add_service_listener ----

    def add_service(self, zc, service_type: str, name: str) -> None:
        print(f"[discovery] add_service: {name}")
        import asyncio
        asyncio.create_task(self.handle_service_update(service_type, name))

    def update_service(self, zc, service_type: str, name: str) -> None:
        print(f"[discovery] update_service: {name}")
        import asyncio
        asyncio.create_task(self.handle_service_update(service_type, name))

    def remove_service(self, zc, service_type: str, name: str) -> None:
        print(f"[discovery] remove_service: {name}")

    async def handle_service_update(self, service_type: str, name: str):
        if self._stopped or self.aiozc is None:
            return

        print(f"[discovery] service update: {name}")

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

        addresses = info.parsed_addresses()
        # TODO: Add IPV6 support
        ipv4_addresses = [a for a in addresses if "." in a]

        if not ipv4_addresses:
            print(f"[discovery] no IPv4 address for {name}, skipping")
            return

        ip = ipv4_addresses[0]
        port = info.port

        print(f"[discovery] all addresses: {addresses}")
        print(f"[discovery] selected IPv4: {ip}")

        now = time.time()
        last_seen = self._seen.get(remote_id, 0)
        if now - last_seen < 5:
            return
        self._seen[remote_id] = now

        print(f"[discovery] found peer {remote_id} at {ip}:{port}")
        await self._handshake_with_peer(ip, port)

    async def _handshake_with_peer(self, ip: str, port: int):
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

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                print(f"[discovery] attempting handshake with peer {ip}:{port}")

                if self.peer_public_key_pem is not None:
                    encrypted_jwt = security_services.encrypt(self.peer_public_key_pem, payload)
                    request_body = {"encrypted_jwt": encrypted_jwt}
                    r = await client.post(url, json=request_body)
                else:
                    r = await client.post(url, json=payload)

                r.raise_for_status()
                data = r.json()
                print(f"[discovery] handshake with peer {ip}:{port} result: {data}")
        except Exception as e:
            print(f"[discovery] handshake failed with {ip}:{port}: {e}")
            return

        if not data.get("accepted"):
            print(f"[discovery] handshake rejected by {ip}:{port}: {data.get('reason')}")
            return

        if ip not in self.peer_list:
            self.peer_list.append(ip)
            print(f"[discovery] added peer {ip} to peer_list")

        print(
            f"[discovery] handshake accepted by "
            f"{data.get('device_name')} ({data.get('device_id')}) at {ip}:{port}"
        )