import socket
import threading
import time
from typing import Optional

import httpx
from zeroconf import IPVersion, ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf


class LanClipboardListener(ServiceListener):
    def __init__(self, discovery_service: "LanClipboardDiscovery"):
        self.discovery_service = discovery_service

    def add_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        self.discovery_service.handle_service_update(service_type, name)

    def update_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        self.discovery_service.handle_service_update(service_type, name)

    def remove_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        print(f"[discovery] service removed: {name}")


class LanClipboardDiscovery:
    SERVICE_TYPE = "_lanclipboard._tcp.local."

    def __init__(
        self,
        local_id: str,
        device_name: str,
        platform_name: str,
        port: int,
        protocol_version: int = 1,
    ):
        self.local_id = local_id
        self.device_name = device_name
        self.platform_name = platform_name
        self.port = port
        self.protocol_version = protocol_version

        self.zeroconf: Optional[Zeroconf] = None
        self.service_info: Optional[ServiceInfo] = None
        self.browser: Optional[ServiceBrowser] = None

        self._stop_event = threading.Event()
        self._handshake_lock = threading.Lock()
        self._seen = {}  # device_id -> last_seen_ts

    def start(self):
        self.zeroconf = Zeroconf(ip_version=IPVersion.All)

        ip_addr = self._get_local_ip()
        if not ip_addr:
            raise RuntimeError("Could not determine local IP for Zeroconf advertisement")

        properties = {
            b"device_id": self.local_id.encode("utf-8"),
            b"device_name": self.device_name.encode("utf-8"),
            b"platform": self.platform_name.encode("utf-8"),
            b"protocol_version": str(self.protocol_version).encode("utf-8"),
        }

        service_name = f"{self.device_name}.{self.SERVICE_TYPE}"

        self.service_info = ServiceInfo(
            type_=self.SERVICE_TYPE,
            name=service_name,
            addresses=[socket.inet_aton(ip_addr)],
            port=self.port,
            properties=properties,
            server=f"{socket.gethostname()}.local.",
        )

        self.zeroconf.register_service(self.service_info)
        print(f"[discovery] registered {service_name} at {ip_addr}:{self.port}")

        listener = LanClipboardListener(self)
        self.browser = ServiceBrowser(self.zeroconf, self.SERVICE_TYPE, listener=listener)
        print("[discovery] browser started")

    def stop(self):
        self._stop_event.set()

        if self.browser is not None:
            self.browser.cancel()

        if self.zeroconf is not None and self.service_info is not None:
            try:
                self.zeroconf.unregister_service(self.service_info)
            except Exception as e:
                print(f"[discovery] unregister failed: {e}")

        if self.zeroconf is not None:
            self.zeroconf.close()

        print("[discovery] stopped")

    def handle_service_update(self, service_type: str, name: str):
        if self._stop_event.is_set() or self.zeroconf is None:
            return

        info = self.zeroconf.get_service_info(service_type, name)
        if info is None:
            return

        props = {
            (k.decode("utf-8") if isinstance(k, bytes) else k):
            (v.decode("utf-8") if isinstance(v, bytes) else v)
            for k, v in info.properties.items()
        }

        remote_id = props.get("device_id")
        if not remote_id or remote_id == self.local_id:
            return

        addresses = info.parsed_addresses()
        if not addresses:
            return

        ip = addresses[0]
        port = info.port

        with self._handshake_lock:
            now = time.time()
            last_seen = self._seen.get(remote_id, 0)
            if now - last_seen < 5:
                return
            self._seen[remote_id] = now

        print(f"[discovery] found peer {remote_id} at {ip}:{port}")
        self._handshake_with_peer(ip, port)

    def _handshake_with_peer(self, ip: str, port: int):
        url = f"http://{ip}:{port}/api/handshake"

        payload = {
            "device_id": self.local_id,
            "device_name": self.device_name,
            "platform": self.platform_name,
            "protocol_version": self.protocol_version,
            "supports_text": True,
            "supports_files": True,
            "supports_encryption": False,
        }

        try:
            with httpx.Client(timeout=3.0) as client:
                print(f'attempting handshake with peer {ip}:{port}')
                r = client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
                print(f'handshake with peer {ip}:{port} result: {data}')
        except Exception as e:
            print(f"[discovery] handshake failed with {ip}:{port}: {e}")
            return

        if not data.get("accepted"):
            print(f"[discovery] handshake rejected by {ip}:{port}: {data.get('reason')}")
            return

        print(
            f"[discovery] handshake accepted by "
            f"{data.get('device_name')} ({data.get('device_id')}) at {ip}:{port}"
        )

    @staticmethod
    def _get_local_ip() -> Optional[str]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return None