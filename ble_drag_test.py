#!/usr/bin/env python3
"""One-minute PM5 drag-factor comparison: observational, no PM5 writes."""
import argparse
import asyncio
import statistics
import time
from bleak import BleakClient, BleakScanner

BASE = "-43e5-11e4-916c-0800200c9a66"
GENERAL = "ce060031" + BASE
ADDITIONAL = "ce060032" + BASE
POWER = "ce060036" + BASE

async def run(args):
    found = {}
    def detect(device, adv):
        name = adv.local_name or device.name or ""
        if "pm5" in name.lower():
            found[device.address] = (device, name)
    print("Wake the PM5 with Menu. Scanning...", flush=True)
    for _ in range(3):
        async with BleakScanner(detection_callback=detect):
            await asyncio.sleep(15)
        match = [(d, n) for d, n in found.values() if args.name.lower() in n.lower()]
        if match:
            break
        print("Not found. Keep PM5 awake.", flush=True)
    if len(match) != 1:
        print("Require exactly one matching PM5. Use --name with its number.")
        return
    device, name = match[0]
    print(f"Connecting to {name} ...", flush=True)
    samples = []
    watts = []
    drag = []
    cadence = []
    state = {"distance": None, "start": None, "last": None, "elapsed": None}
    def notify(char, data):
        b = bytes(data)
        prefix = char.uuid.split("-")[0].lower()
        if prefix == "ce060031" and len(b) >= 19:
            meters = int.from_bytes(b[3:6], "little") / 10
            elapsed = int.from_bytes(b[:3], "little") / 100
            df = b[18]
            if df not in (0, 255):
                drag.append(df)
            previous = state["last"]
            state["last"] = meters
            state["elapsed"] = elapsed
            if state["start"] is None and previous is not None and meters > previous:
                state["start"] = time.monotonic()
                state["distance"] = previous
                print("Movement detected. Measurement started!", flush=True)
            if state["start"] is not None:
                duration = time.monotonic() - state["start"]
                if duration <= args.seconds:
                    samples.append((duration, meters))
        elif prefix == "ce060032" and len(b) >= 6 and state["start"] is not None:
            spm = b[5]
            if spm not in (0, 255):
                cadence.append(spm)
        elif prefix == "ce060036" and len(b) >= 5 and state["start"] is not None:
            w = int.from_bytes(b[3:5], "little")
            if w > 0:
                watts.append(w)
    client = BleakClient(device, timeout=30)
    try:
        await client.connect()
        print("CONNECTED. Ready: start rowing when you want.", flush=True)
        for uuid in (GENERAL, ADDITIONAL, POWER):
            await client.start_notify(uuid, notify)
        deadline = time.monotonic() + 90
        last_print = 0
        while time.monotonic() < deadline:
            await asyncio.sleep(0.25)
            started = state["start"]
            if started is None:
                continue
            elapsed = time.monotonic() - started
            if elapsed - last_print >= 5:
                last_print = elapsed
                d = samples[-1][1] - state["distance"] if samples else 0
                print(f"{elapsed:.0f}s: +{d:.1f}m drag={drag[-1] if drag else '?'}", flush=True)
            if elapsed >= args.seconds:
                break
    finally:
        if client.is_connected:
            await client.disconnect()
    if not samples or state["distance"] is None:
        print("No movement captured. Try again.")
        return
    duration, final = samples[-1]
    distance = max(0, final - state["distance"])
    print(f"RESULT {args.label}: {distance:.1f}m in {duration:.1f}s; "
          f"drag median={statistics.median(drag) if drag else 'N/A'}; "
          f"cadence mean={statistics.mean(cadence):.1f}spm" if cadence else
          f"RESULT {args.label}: {distance:.1f}m in {duration:.1f}s; drag median={statistics.median(drag) if drag else 'N/A'}; cadence=N/A")
    print(f"Stroke power mean (not time-weighted)={statistics.mean(watts):.1f}W" if watts else "Stroke power=N/A")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="", help="PM5 number, e.g. 431370503")
    p.add_argument("--seconds", type=int, default=60)
    p.add_argument("--label", default="test")
    args = p.parse_args()
    asyncio.run(run(args))
