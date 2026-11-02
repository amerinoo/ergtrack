"""Shared read-only BLE transport and PM5 metric decoder for ergtrack."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
import time

BASE = "-43e5-11e4-916c-0800200c9a66"
GENERAL = "ce060031" + BASE
ADDITIONAL = "ce060032" + BASE
POWER = "ce060036" + BASE

@dataclass(frozen=True)
class PM5Metric:
    kind: str
    received_at: float
    distance_m: float | None = None
    elapsed_s: float | None = None
    drag_factor: int | None = None
    cadence_spm: int | None = None
    watts: int | None = None

def decode_notification(uuid, data, received_at=None):
    """Parse packets used in our validated BLE experiments; ignore truncated data."""
    b = bytes(data)
    prefix = uuid.split("-")[0].lower()
    now = time.monotonic() if received_at is None else received_at
    if prefix == "ce060031" and len(b) >= 19:
        drag = b[18]
        return PM5Metric("general", now, distance_m=int.from_bytes(b[3:6], "little") / 10,
                         elapsed_s=int.from_bytes(b[:3], "little") / 100,
                         drag_factor=drag if drag not in (0, 255) else None)
    if prefix == "ce060032" and len(b) >= 6:
        cadence = b[5]
        return PM5Metric("additional", now,
                         cadence_spm=cadence if cadence not in (0, 255) else None)
    if prefix == "ce060036" and len(b) >= 5:
        return PM5Metric("power", now, watts=int.from_bytes(b[3:5], "little"))
    return None

async def discover_pm5(name="", scans=3, scan_seconds=15):
    try:
        from bleak import BleakScanner
    except ImportError as exc:
        raise RuntimeError("Install bleak: python -m pip install bleak") from exc
    found = {}
    def detect(device, adv):
        label = adv.local_name or device.name or ""
        if "pm5" in label.lower() and name.lower() in label.lower():
            found[device.address] = (device, label)
    print("Wake PM5 with Menu. Scanning...", flush=True)
    for _ in range(scans):
        async with BleakScanner(detection_callback=detect):
            await asyncio.sleep(scan_seconds)
        if found:
            break
        print("No PM5 detected yet; keep the monitor awake.", flush=True)
    return sorted(found.values(), key=lambda pair: pair[1])

def choose_pm5(devices):
    if not devices:
        raise RuntimeError("No PM5 found. Wake the monitor and try again.")
    if len(devices) == 1:
        print(f"Found one PM5: {devices[0][1]}. Selecting automatically.")
        return devices[0]
    print("Several PM5 monitors found:")
    for i, (_, name) in enumerate(devices, 1):
        print(f"  {i}. {name}")
    while True:
        selection = input(f"Choose PM5 [1-{len(devices)}], or q: ").strip()
        if selection.lower() == "q":
            raise RuntimeError("Selection cancelled")
        if selection.isdigit() and 1 <= int(selection) <= len(devices):
            return devices[int(selection) - 1]
        print("Invalid option.")

class PM5Connection:
    """Async context manager yielding decoded notifications to a callback."""
    def __init__(self, callback, name="", interactive=True, on_status=None):
        self.callback = callback
        self.on_status = on_status or (lambda status: None)
        self.name = name
        self.interactive = interactive
        self.client = None

    async def __aenter__(self):
        try:
            from bleak import BleakClient
        except ImportError as exc:
            raise RuntimeError("Install bleak: python -m pip install bleak") from exc
        self.on_status("BUSCANDO PM5")
        devices = await discover_pm5(self.name)
        if self.interactive:
            device, label = choose_pm5(devices)
        else:
            if len(devices) != 1:
                raise RuntimeError(f"Expected exactly one PM5, found {len(devices)}")
            device, label = devices[0]
        self.on_status("CONECTANDO PM5")
        print(f"Connecting to {label} ...", flush=True)
        self.client = BleakClient(device, timeout=30)
        await self.client.connect()
        try:
            def notify(characteristic, data):
                metric = decode_notification(characteristic.uuid, data)
                if metric is not None:
                    self.callback(metric)
            for uuid in (GENERAL, ADDITIONAL, POWER):
                await self.client.start_notify(uuid, notify)
        except Exception:
            await self.client.disconnect()
            raise
        self.on_status("PM5 CONECTADO")
        print("CONNECTED.", flush=True)
        return self

    async def __aexit__(self, *_):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
        self.on_status("DESCONECTADO")
