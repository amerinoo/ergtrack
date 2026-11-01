# ErgTrack gateway — First BLE discovery experiment

This is a **diagnostic**, not yet an autonomous gateway. No BLE connection, pairing or GATT reads happen in this test.

## Prepare on macOS

```bash
git pull
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-ble.txt
python ble_scan.py --seconds 45 --jsonl scan-off.jsonl
```

With the PM5 awake and at its normal main/workout screen, do **not** choose Turn Wireless ON. Note whether the PM5 is visible.

Then, solely as a comparison, choose PM5 **More Options → Turn Wireless ON** and run:

```bash
python ble_scan.py --seconds 45 --jsonl scan-on.jsonl
```

If the monitor is discoverable only in the second case, this is a significant blocker to a self-service, zero-touch deployment. Further investigation would be needed before selecting gateway hardware.

Note: an unnamed BLE device may be the monitor. Capture the logs and compare new identifiers before/after wireless activation. macOS CoreBluetooth device IDs are local UUIDs, not hardware MAC addresses, and might differ between Macs. Do not assume the ID can be printed on a globally stable QR.

First macOS run may ask for Terminal/Python Bluetooth permission. Allow it; if blocked see System Settings > Privacy & Security > Bluetooth.

## Record

- PM5 model, firmware version
- Awake on normal screen: detected / not detected
- After Turn Wireless ON: detected / not detected
- Same identifier on repeated scans: yes / no
- After sleep and wake without changing menu: detected / not detected
- Are other devices, e.g. ErgData, connected?

JSONL files can include nearby device identifiers. **Do not publish raw scan logs in a public GitHub repository.**

## Next technical gate

Only after discovery is understood: implement GATT connection and subscriptions, then reconnect tests, multi-PM5 tests, station-to-QR mapping, and Safari/PWA WebSocket integration.

Concept2 PM5 Bluetooth communication specification: https://www.concept2.cn/files/pdf/us/monitors/PM5_BluetoothSmartInterfaceDefinition.pdf

Bleak on macOS: https://bleak.readthedocs.io/en/latest/backends/macos.html
