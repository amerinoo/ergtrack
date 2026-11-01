# First observed PM5 wake-up test — 2026-11-01

## Observed by user at The Box

- The PM5 was initially asleep.
- Pressing **Menu only** woke the PM5.
- The Mac BLE scanner then discovered **PM5 431369979 Row**.
- RSSI was **-43 dBm**.
- Advertised services included:
  - `00001826-0000-1000-8000-00805f9b34fb` (Fitness Machine Service)
  - `ce060000-43e5-11e4-916c-0800200c9a66` (Concept2)
- No manual `Turn Wireless ON` menu action was needed **in this observation**.

## Interpretation

**PASS (preliminary):** advertisement observed on wake-up without manual wireless activation.
**NOT YET VALIDATED:** repeated cold/warm wake-up reliability, active GATT connection, metrics, reconnection after sleep, simultaneous PM5s, and unattended self-service.

## Next test

```bash
git pull
source .venv/bin/activate
pip install -r requirements-ble.txt
python ble_gatt_probe.py
```

Wake PM5 using Menu before command. The probe will list services and characteristic properties **without sending commands or subscribing**. Share output; exclude identifiers if desired.
