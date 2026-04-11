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

- Run on all devices
- Ensure same LAN
- Wait for a handshake

## Troubleshooting

- Check firewall
- Verify port 8000 or prot configured in the config application
- If security is enabled, ensure that the same key archive is used across Lan Clipboard instances
- Wayland clipboard sync may run into issues. To fix that, try restarting (via stop and start buttons in the configurator)