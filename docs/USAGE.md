# Usage Guide

## Start the App

1. Open config UI:
   python config_ui.py

2. Configure:
   - Network
   - Security
   - Hotkeys

3. Start the service

## Multi-device setup

- Run the service on all devices.
- Ensure the devices can reach each other over HTTP on the configured port.
- Prefer `network.bootstrap_peers` in `config/config.yaml` for reliable cross-platform setup.
- Leave `network.discovery: true` enabled if you want mDNS as a best-effort convenience layer.

Example:

```yaml
network:
  port: 8000
  discovery: true
  bootstrap_peers:
    - 192.168.100.53
    - 192.168.100.64
```

## Troubleshooting

- Check firewall
- Verify port 8000 or prot configured in the config application
- If security is enabled, ensure that the same key archive is used across Lan Clipboard instances
- Wayland clipboard sync may run into issues. To fix that, try restarting (via stop and start buttons in the configurator)
- If mDNS discovery does not find peers, verify Avahi/Bonjour and use `bootstrap_peers` instead of relying on multicast discovery alone.
- On Windows, prefer `Ctrl + Shift + Insert` over `Ctrl + Shift + V`. The `Ctrl + Shift + V` chord is not reliably delivered to the global keyboard listener on all systems/apps.
