#!/usr/bin/env python3
"""Connect to multiple PM5s and independently record live metrics (no writes)."""
import argparse
import asyncio
import time
from bleak import BleakClient, BleakScanner

BASE = "-43e5-11e4-916c-0800200c9a66"
GENERAL = "ce060031" + BASE
ADDITIONAL = "ce060032" + BASE
POWER = "ce060036" + BASE

async def monitor(device, seconds, state, connection_gate):
    name = device.name or "PM5"
    key = device.address[-8:]
    last_print = 0.0
    def on_data(char, payload):
        nonlocal last_print
        raw = bytes(payload)
        uid = str(char.uuid).split("-")[0].lower()
        data = state[key]
        data["last_seen"] = time.monotonic()
        if uid == "ce060031" and len(raw) >= 6:
            data["distance"] = int.from_bytes(raw[3:6], "little") / 10
            data["elapsed"] = int.from_bytes(raw[:3], "little") / 100
            if data["baseline"] is None:
                data["baseline"] = data["distance"]
            if data["distance"] < data["baseline"]:
                data["baseline"] = data["distance"]
            data["relative"] = max(0, data["distance"] - data["baseline"])
        elif uid == "ce060032" and len(raw) >= 6:
            data["speed"] = int.from_bytes(raw[3:5], "little") / 1000
            data["cadence"] = raw[5]
        elif uid == "ce060036" and len(raw) >= 5:
            data["power"] = int.from_bytes(raw[3:5], "little")
        now = time.monotonic()
        if now - last_print >= 1 and data["distance"] is not None:
            last_print = now
            print(f"{name} [{key}]  +{data['relative']:.1f}m "
                  f"(PM5={data['distance']:.1f}m) "
                  f"speed={data['speed']}m/s cadence={data['cadence']}spm "
                  f"power={data['power']}W", flush=True)
    try:
        client = BleakClient(device, timeout=30)
        async with connection_gate:
            print(f"CONNECTING {name} [{key}]", flush=True)
            await client.connect()
        try:
            print(f"CONNECTED {name} [{key}]", flush=True)
            for uuid in (GENERAL, ADDITIONAL, POWER):
                await client.start_notify(uuid, on_data)
            await asyncio.sleep(seconds)
            for uuid in (GENERAL, ADDITIONAL, POWER):
                await client.stop_notify(uuid)
            print(f"FINISHED {name} [{key}]", flush=True)
        finally:
            if client.is_connected:
                await client.disconnect()
    except Exception as exc:
        print(f"ERROR {name} [{key}]: {type(exc).__name__}: {exc}", flush=True)

async def run(count, seconds, scan_seconds, scan_rounds):
    print("Wake the PM5 monitors with Menu; scanning...", flush=True)
    known = {}
    for attempt in range(1, scan_rounds + 1):
        found = await BleakScanner.discover(timeout=scan_seconds)
        for device in found:
            if "pm5" in (device.name or "").lower():
                known[device.address] = device
        print(f"Scan {attempt}/{scan_rounds}: {len(known)} unique named PM5(s) seen", flush=True)
        if len(known) >= count:
            break
        if attempt < scan_rounds:
            print("Still searching; wake missing PM5s with Menu (no rowing required).", flush=True)
    devices = list(known.values())
    print(f"Found {len(devices)} named PM5(s):")
    for dev in devices:
        print(f"  {dev.name} ({dev.address})")
    if len(devices) < count:
        print(f"Need at least {count} PM5s. Wake more monitors and retry.")
        return 1
    selected = devices[:count]
    state = {
        d.address[-8:]: {
            "baseline": None, "distance": None, "elapsed": None,
            "relative": 0.0, "speed": None, "cadence": None,
            "power": None, "last_seen": None,
        }
        for d in selected
    }
    connection_gate = asyncio.Semaphore(1)  # Serialize GATT connect attempts on macOS.
    results = await asyncio.gather(*(monitor(d, seconds, state, connection_gate) for d in selected), return_exceptions=True)
    print("SUMMARY")
    for device in selected:
        d = state[device.address[-8:]]
        print(f"{device.name}: relative={d['relative']:.1f}m "
              f"last_distance={d['distance']}m")
    for err in results:
        if isinstance(err, BaseException):
            print(f"Unexpected task error: {err}")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--scan-seconds", type=int, default=20, help="Duration of each discovery scan")
    parser.add_argument("--scan-rounds", type=int, default=3, help="Maximum discovery attempts")
    opts = parser.parse_args()
    if min(opts.count, opts.seconds, opts.scan_seconds, opts.scan_rounds) < 1:
        parser.error("--count and --seconds must be positive")
    raise SystemExit(asyncio.run(run(opts.count, opts.seconds, opts.scan_seconds, opts.scan_rounds)))
