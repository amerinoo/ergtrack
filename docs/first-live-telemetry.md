# PM5 BLE live telemetry — first successful hardware observation (2026-11-01)

The user ran `python ble_live.py --seconds 30` on a Mac connected directly over BLE to **PM5 431369979 Row**.

## Observed outcomes

- Discovery and GATT connection succeeded automatically after waking with Menu.
- Notifications enabled for Concept2 characteristics `ce060031`, `ce060032`, `ce060035`.
- Elapsed time increased from 0 to 16.09 seconds.
- Distance increased from 0 to **27.0 m**, showing useful live telemetry.
- Additional status showed speed increasing from 0 to approx **2.216 m/s**, with stroke rate values requiring confirmation against PM5 display.
- Stroke data arrived on `0x35` during activity.
- Output continued repeating the final 16.09s / 27.0m samples after rowing ended.
- In this test, notifications appeared about once per second for 0x31/0x32; actual update cadence must be measured rigorously.

## Validated

- PM5 BLE advertising after wake without manual wireless-menu action (one observed case).
- Mac connection to the PM5 via GATT.
- Active notifications with plausible elapsed-time, distance, and speed data.

## Still open

- Cross-check displayed PM5 metrics and cadence; interpretation and sampling.
- 0x36 stroke power notifications (newly added; hardware untested).
- Automatic recovery after PM5 sleep, gateway reboot and movement.
- Reliable identity/QR assignment across reboots and gateway machines.
- Two then four then eight+ simultaneous PM5s.
- Collision with ErgData/other BLE clients.
- iPhone PWA received telemetry via local gateway WebSocket.

## Next test

```bash
git pull
source .venv/bin/activate
python ble_live.py --seconds 45
```

Row for approximately 20 seconds, then stop. Observe whether `STROKE_POWER watts=...` values appear and whether they match the PM5 display. Repeat a wake-from-sleep test later.

Do not publish raw logs containing customer identifiers.
