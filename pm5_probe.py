#!/usr/bin/env python3
"""Read-only Concept2 PM5 USB HID / CSAFE connectivity diagnostic.

No workout configuration commands are sent. Hardware validation pending.
"""
import argparse
import sys
import time

try:
    import hid
except ImportError:
    sys.exit("Missing dependency. Run: python -m pip install -r requirements.txt")

VENDOR_ID = 0x17A4  # Concept2 USB vendor ID
CSAFE_START = 0xF1
CSAFE_STOP = 0xF2
GET_VERSION = 0x91  # CSAFE_GETVERSION_CMD
REPORT_ID = 2
REPORT_SIZE = 120


def devices():
    return [
        d for d in hid.enumerate()
        if d.get("vendor_id") == VENDOR_ID
        or "concept2" in str(d.get("manufacturer_string") or "").lower()
    ]


def print_devices(found):
    if not found:
        print("No Concept2 HID device detected.")
        print("Try: system_profiler SPUSBDataType")
        return
    for i, d in enumerate(found):
        print(f"[{i}] {d.get('manufacturer_string')} / {d.get('product_string')}")
        print(f"    VID:PID={d['vendor_id']:04x}:{d['product_id']:04x} "
              f"interface={d.get('interface_number')} usage={d.get('usage')}")
        print(f"    path={d.get('path')!r}")


def frame(command):
    # Standard CSAFE: start + commands + XOR checksum + stop.
    return bytes([CSAFE_START, command, command, CSAFE_STOP])


def probe(device_info, timeout_ms):
    handle = hid.device()
    try:
        handle.open_path(device_info["path"])
        payload = frame(GET_VERSION)
        report = bytes([REPORT_ID]) + payload.ljust(REPORT_SIZE, b"\x00")
        print(f"TX CSAFE: {payload.hex(' ')}")
        written = handle.write(report)
        print(f"HID bytes written: {written}")
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            response = handle.read(REPORT_SIZE + 1, 300)
            if response:
                raw = bytes(response)
                print(f"RX HID ({len(raw)} bytes): {raw.hex(' ')}")
                # Report framing varies with platform/PM firmware;
                # preserve raw bytes for validation before parsing.
                if CSAFE_START in raw or 0xF0 in raw:
                    print("Possible CSAFE response detected; inspect raw bytes.")
                return 0
        print("No HID response before timeout. Confirm firmware and report format.")
        return 2
    finally:
        handle.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true")
    group.add_argument("--probe", action="store_true")
    parser.add_argument("--device", type=int, default=0, help="index from --list")
    parser.add_argument("--timeout-ms", type=int, default=2000)
    args = parser.parse_args()

    found = devices()
    print_devices(found)
    if args.list:
        return 0 if found else 1
    if not found or not 0 <= args.device < len(found):
        print("Invalid device index, or no device available.", file=sys.stderr)
        return 1
    try:
        return probe(found[args.device], args.timeout_ms)
    except OSError as exc:
        print(f"USB/HID error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
