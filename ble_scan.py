#!/usr/bin/env python3
"""ErgTrack BLE discovery diagnostic (no pairing or connection).

Usage:
  python ble_scan.py --seconds 30
  python ble_scan.py --seconds 90 --jsonl observations.jsonl
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone

from bleak import BleakScanner


def record(device, advertisement):
    name = advertisement.local_name or device.name or ""
    services = list(advertisement.service_uuids)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "identifier": device.address,
        "name": name,
        "rssi": advertisement.rssi,
        "services": services,
        "manufacturer_ids": sorted(advertisement.manufacturer_data),
    }


def is_candidate(value):
    name = value["name"].lower()
    # Initial heuristic; save *all* devices to JSONL so we don't miss unnamed PM5s.
    return any(keyword in name for keyword in ("pm5", "concept2", "rowerg", "skierg"))


async def scan(seconds, jsonl_path, all_devices):
    seen = {}
    output = open(jsonl_path, "a", encoding="utf-8") if jsonl_path else None

    def on_detect(device, advertisement):
        value = record(device, advertisement)
        key = value["identifier"]
        first = key not in seen
        seen[key] = value
        if output:
            output.write(json.dumps(value) + "\n")
            output.flush()
        if first or is_candidate(value) or all_devices:
            label = "PM5?" if is_candidate(value) else "BLE"
            print(f"[{label}] {value['name'] or '(no name)'} | "
                  f"id={key} | RSSI={value['rssi']} dBm | "
                  f"services={','.join(value['services']) or '-'}", flush=True)

    try:
        print(f"Scanning for {seconds}s. Wake the PM5 during the scan; "
              "do not enable wireless yet.", flush=True)
        async with BleakScanner(detection_callback=on_detect):
            await asyncio.sleep(seconds)
        print(f"Observed {len(seen)} unique BLE devices.")
        candidates = [x for x in seen.values() if is_candidate(x)]
        print(f"Named PM5 candidates: {len(candidates)}")
        if not candidates:
            print("No named PM5 found. This does NOT prove it was absent; "
                  "check unnamed devices/JSONL and repeat with Wireless ON.")
    finally:
        if output:
            output.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--jsonl", help="Optional detailed local log (may contain device identifiers)")
    parser.add_argument("--all", action="store_true", help="Print repeated observations from all BLE devices")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    try:
        asyncio.run(scan(args.seconds, args.jsonl, args.all))
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f"Bluetooth scan error: {exc}\n"
                    "Check macOS Settings > Privacy & Security > Bluetooth for Terminal/Python.\n")


if __name__ == "__main__":
    main()
