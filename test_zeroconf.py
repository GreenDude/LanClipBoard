import asyncio
from zeroconf import IPVersion
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

SERVICE_TYPE = "_lanclipboard._tcp.local."

class Listener:
    def add_service(self, zc, service_type, name):
        print("[add]", name)
        asyncio.create_task(self.resolve(zc, service_type, name))

    def update_service(self, zc, service_type, name):
        print("[update]", name)
        asyncio.create_task(self.resolve(zc, service_type, name))

    def remove_service(self, zc, service_type, name):
        print("[remove]", name)

    async def resolve(self, zc, service_type, name):
        info = AsyncServiceInfo(service_type, name)
        ok = await info.async_request(zc, timeout=3000)
        print("[resolve]", name, "ok=", ok)
        if ok:
            print("  addresses:", info.parsed_addresses())
            print("  port:", info.port)
            print("  props:", info.properties)

async def main():
    aiozc = AsyncZeroconf(ip_version=IPVersion.V4Only)
    listener = Listener()
    await aiozc.async_add_service_listener(SERVICE_TYPE, listener)
    print("Listening for", SERVICE_TYPE)
    try:
        await asyncio.sleep(30)
    finally:
        await aiozc.async_close()

asyncio.run(main())