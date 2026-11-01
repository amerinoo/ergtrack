#!/usr/bin/env python3
"""Read-only live PM5 BLE notifications (Concept2 custom GATT).

No CSAFE writes, no workout changes. Start rowing after connecting.
"""
import argparse
import asyncio
import time
from bleak import BleakScanner, BleakClient

BASE = "-43e5-11e4-916c-0800200c9a66"
GENERAL = "ce060031" + BASE
ADDITIONAL = "ce060032" + BASE
STROKE = "ce060035" + BASE
STROKE_POWER = "ce060036" + BASE

def u24(b):
    return int.from_bytes(b, "little")

async def main(seconds):
    print("Searching for PM5 ...", flush=True)
    found = await BleakScanner.discover(timeout=12)
    matches = [d for d in found if "pm5" in (d.name or "").lower()]
    if not matches:
        print("PM5 not found. Press Menu to wake it and retry.")
        return
    device = matches[0]
    print(f"Connecting: {device.name} ({device.address})", flush=True)
    last = {}
    def callback(sender, payload):
        b = bytes(payload)
        suffix = str(sender.uuid).split("-")[0].lower()
        now = time.monotonic()
        previous = last.get(suffix, 0)
        if now - previous < 0.3:
            return
        last[suffix] = now
        if suffix == "ce060031" and len(b) >= 6:
            elapsed = u24(b[:3]) / 100
            distance = u24(b[3:6]) / 10
            print(f"GENERAL time={elapsed:.2f}s distance={distance:.1f}m raw={b.hex(' ')}", flush=True)
        elif suffix == "ce060032" and len(b) >= 6:
            speed = int.from_bytes(b[3:5], "little") / 1000
            cadence = b[5]
            print(f"ADDITIONAL speed={speed:.3f}m/s cadence={cadence}spm raw={b.hex(' ')}", flush=True)
        elif suffix == "ce060036" and len(b) >= 5:
            watts = int.from_bytes(b[3:5], "little")
            print(f"STROKE_POWER watts={watts}W raw={b.hex(' ')}", flush=True)
        else:
            print(f"{suffix} raw={b.hex(' ')}", flush=True)

    async with BleakClient(device, timeout=20) as client:
        print("Connected. Subscribing to 0x31/0x32/0x35/0x36; row for a few strokes.", flush=True)
        active = []
        for uuid in (GENERAL, ADDITIONAL, STROKE, STROKE_POWER):
            try:
                await client.start_notify(uuid, callback)
                active.append(uuid)
                print("Notifications enabled:", uuid[:8], flush=True)
            except Exception as error:
                print(f"Cannot subscribe {uuid[:8]}: {type(error).__name__}: {error}", flush=True)
        if active:
            await asyncio.sleep(seconds)
        else:
            print("No subscriptions available.")
        for uuid in active:
            try:
                await client.stop_notify(uuid)
            except Exception:
                pass
    print("Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(main(args.seconds))
