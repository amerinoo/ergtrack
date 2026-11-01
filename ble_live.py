#!/usr/bin/env python3
"""Read-only live PM5 BLE notifications (Concept2 custom GATT).

No CSAFE writes, no workout changes. Start rowing or skiing after connecting.
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

async def main(seconds, name, scan_seconds, scan_rounds):
    print(f"Searching for PM5 matching {name!r} ...", flush=True)
    discovered = {}
    for attempt in range(1, scan_rounds + 1):
        found = await BleakScanner.discover(timeout=scan_seconds)
        for device in found:
            device_name = device.name or ""
            if "pm5" in device_name.lower():
                discovered[device.address] = device
        print(f"Scan {attempt}/{scan_rounds}: {len(discovered)} PM5(s) found", flush=True)
        for item in discovered.values():
            print(f"  {item.name} ({item.address})", flush=True)
        matches = [d for d in discovered.values() if name.lower() in (d.name or "").lower()]
        if matches:
            break
        print("Target not seen; press Menu on the PM5 and keep it awake.", flush=True)
    else:
        print(f"No PM5 matched {name!r} after {scan_rounds} scans.")
        return
    if len(matches) > 1:
        print("Multiple PM5s match: specify --name with the monitor number to avoid selecting the wrong machine.")
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
    parser.add_argument("--name", default="", help="Part of PM5 name, e.g. 431970273 or Ski")
    parser.add_argument("--scan-seconds", type=int, default=20)
    parser.add_argument("--scan-rounds", type=int, default=3)
    args = parser.parse_args()
    if min(args.seconds, args.scan_seconds, args.scan_rounds) <= 0:
        parser.error("Durations and scan rounds must be positive")
    asyncio.run(main(args.seconds, args.name, args.scan_seconds, args.scan_rounds))
