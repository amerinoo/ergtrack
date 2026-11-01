#!/usr/bin/env python3
"""One-minute PM5 drag-factor comparison using shared read-only BLE transport."""
import argparse
import asyncio
import statistics
import time
from pm5_ble import PM5Connection

async def run(args):
    distances = []
    watts = []
    drags = []
    cadence = []
    state = {"start":None, "start_distance":None, "last_distance":None}
    def metric_received(metric):
        if metric.kind == "general":
            meters = metric.distance_m
            previous = state["last_distance"]
            state["last_distance"] = meters
            if metric.drag_factor is not None:
                drags.append(metric.drag_factor)
            if state["start"] is None and previous is not None and meters > previous:
                state["start"] = time.monotonic()
                state["start_distance"] = previous
                print("Movement detected. Measurement started!", flush=True)
            if state["start"] is not None:
                duration = time.monotonic() - state["start"]
                if duration <= args.seconds:
                    distances.append((duration, meters))
        elif metric.kind == "additional" and state["start"] is not None:
            if metric.cadence_spm is not None:
                cadence.append(metric.cadence_spm)
        elif metric.kind == "power" and state["start"] is not None:
            if metric.watts > 0:
                watts.append(metric.watts)
    async with PM5Connection(metric_received, args.name):
        print("Ready: start rowing when you want.", flush=True)
        deadline = time.monotonic() + 90
        last_print = 0
        while time.monotonic() < deadline:
            await asyncio.sleep(.25)
            started = state["start"]
            if started is None:
                continue
            elapsed = time.monotonic() - started
            if elapsed - last_print >= 5:
                last_print = elapsed
                distance = distances[-1][1] - state["start_distance"] if distances else 0
                print(f"{elapsed:.0f}s: +{distance:.1f}m drag={drags[-1] if drags else '?'}", flush=True)
            if elapsed >= args.seconds:
                break
    if not distances or state["start_distance"] is None:
        print("No movement captured. Try again.")
        return
    duration, final = distances[-1]
    distance = max(0, final - state["start_distance"])
    print(f"RESULT {args.label}: {distance:.1f}m in {duration:.1f}s; drag median={statistics.median(drags) if drags else 'N/A'}; cadence mean={statistics.mean(cadence):.1f}spm" if cadence else
          f"RESULT {args.label}: {distance:.1f}m in {duration:.1f}s; drag median={statistics.median(drags) if drags else 'N/A'}; cadence=N/A")
    print(f"Stroke power mean (not time-weighted)={statistics.mean(watts):.1f}W" if watts else "Stroke power=N/A")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="", help="optional PM5 name filter")
    p.add_argument("--seconds", type=int, default=60)
    p.add_argument("--label", default="test")
    asyncio.run(run(p.parse_args()))
