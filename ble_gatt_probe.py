#!/usr/bin/env python3
"""Discover and inspect GATT services on a Concept2 PM5; no writes or pairing.

Run: python ble_gatt_probe.py
"""
import argparse
import asyncio
from bleak import BleakClient, BleakScanner

def match(device, adv):
    name = (adv.local_name or device.name or "").lower()
    return "pm5" in name or "concept2" in name

async def run(seconds, name_filter):
    print(f"Scanning for PM5 ({seconds}s)...", flush=True)
    found = await BleakScanner.discover(timeout=seconds, return_adv=True)
    candidates = [(d, a) for d, a in found.values()
                  if match(d, a) and name_filter.lower() in (a.local_name or d.name or "").lower()]
    if not candidates:
        print("No matching PM5 found. Wake it with Menu and retry.")
        return 1
    device, adv = sorted(candidates, key=lambda item: item[1].rssi, reverse=True)[0]
    print(f"Connecting to {adv.local_name or device.name} ({device.address}), RSSI {adv.rssi} dBm")
    async with BleakClient(device, timeout=20) as client:
        print(f"Connected: {client.is_connected}")
        for service in client.services:
            print(f"SERVICE {service.uuid}: {service.description}")
            for characteristic in service.characteristics:
                print(f"  CHARACTERISTIC {characteristic.uuid} "
                      f"properties={','.join(characteristic.properties)}")
                for descriptor in characteristic.descriptors:
                    print(f"    descriptor {descriptor.uuid}")
        print("GATT discovery complete. No subscriptions, reads or writes performed.")
    return 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument("--name", default="PM5", help="Optional name substring")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args.seconds, args.name))
    except Exception as exc:
        print(f"GATT connection failed: {type(exc).__name__}: {exc}")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
