#!/usr/bin/env python3
"""Reacciona: audio-first Concept2 PM5 game, running locally on macOS."""
from __future__ import annotations
import argparse
import asyncio
from collections import deque
from pm5_ble import PM5Connection
from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
import statistics
import struct
import tempfile
import time
import wave

class MetricStream:
    def __init__(self):
        self.samples = deque(maxlen=2000)
        self.last_rx = 0.0
        self.distance = 0.0

    def update(self, watts, now=None):
        if not math.isfinite(watts) or not 0 <= watts <= 3000:
            return
        now = time.monotonic() if now is None else now
        self.samples.append((now, watts))
        self.last_rx = now

    def recent_power(self, now, window=2.0):
        if not self.samples or now - self.last_rx > 2.5:
            return None
        values = [w for t, w in self.samples if 0 <= now - t <= window]
        return statistics.median(values) if values else None

class Simulator:
    def __init__(self, stream, baseline, seed):
        self.stream = stream
        self.baseline = baseline
        self.rng = random.Random(seed)
        self.virtual_time = time.monotonic()

    async def tick(self, target):
        self.virtual_time += 1
        factor = {"baseline":1, "escape":1.4, "defend":1, "recover":0.6}[target]
        self.stream.update(max(0, self.baseline * factor + self.rng.uniform(-4, 4)), self.virtual_time)

class Audio:
    NOTES = {
        "ready": [(440, .18)],
        "escape": [(880, .18), (1100, .18)],
        "defend": [(540, .32)],
        "recover": [(360, .18), (290, .25)],
        "success": [(740, .1), (988, .18)],
        "fail": [(260, .3)],
        "shield": [(660, .12), (880, .12), (1175, .2)],
        "end": [(660, .15), (880, .15), (990, .3)]
    }
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.temp = tempfile.TemporaryDirectory(prefix="reacciona-")
        self.paths = {}
        for event, notes in self.NOTES.items():
            path = Path(self.temp.name) / f"{event}.wav"
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                raw = bytearray()
                for frequency, duration in notes:
                    length = int(duration * 16000)
                    for i in range(length):
                        envelope = max(0, min(1, i / 250, (length - i) / 250))
                        value = int(12000 * envelope * math.sin(2 * math.pi * frequency * i / 16000))
                        raw.extend(struct.pack("<h", value))
                wav.writeframes(raw)
            self.paths[event] = path

    async def play(self, event):
        if not self.enabled:
            return
        try:
            process = await asyncio.create_subprocess_exec("afplay", str(self.paths[event]))
            await process.wait()
        except FileNotFoundError:
            self.enabled = False
            print("Audio unavailable (afplay missing)", flush=True)

    def close(self):
        self.temp.cleanup()

@dataclass
class Score:
    points: int = 0
    lives: int = 3
    shield: int = 0
    defense_charges: int = 0
    streak: int = 0
    successes: int = 0
    attempts: int = 0

    def apply(self, kind, valid, excellent=False):
        self.attempts += 1
        earned = 0
        shield_gained = False
        if valid:
            self.successes += 1
            self.streak += 1
            earned = 100 + (25 if excellent else 0)
            if self.streak % 3 == 0:
                earned += 50
            if kind == "defend" and not self.shield:
                self.defense_charges += 1
                if self.defense_charges >= 2:
                    self.shield = 1
                    self.defense_charges = 0
                    shield_gained = True
        else:
            self.streak = 0
            if kind == "escape":
                if self.shield:
                    self.shield = 0
                else:
                    self.lives = max(0, self.lives - 1)
        self.points += earned
        return {"earned":earned, "shield_gained":shield_gained}

def judge(kind, powers, baseline):
    if baseline <= 0 or not powers:
        return False, False
    ratios = [p / baseline for p in powers]
    if kind == "escape":
        if len(ratios) < 5:
            return False, False
        hits = sum(r >= 1.30 for r in ratios)
        return hits >= 4, hits / len(ratios) >= 0.9
    if len(ratios) < 8:
        return False, False
    lo, hi = {"defend":(.85, 1.15), "recover":(.45, .75)}[kind]
    hits = sum(lo <= r <= hi for r in ratios)
    return hits / len(ratios) >= .75, hits / len(ratios) >= .9

async def measure(stream, count, simulator, target, interval):
    readings = []
    for _ in range(count):
        if simulator:
            await simulator.tick(target)
            await asyncio.sleep(interval if interval else 0)
        else:
            await asyncio.sleep(interval)
        now = simulator.virtual_time if simulator else time.monotonic()
        power = stream.recent_power(now)
        if power is None:
            return None
        readings.append(power)
    return readings

async def play_game(args, stream, audio, simulator):
    print("CALIBRATION: maintain a comfortable effort for 45 seconds.")
    calibration = await measure(stream, 45, simulator, "baseline", args.tick)
    if not calibration:
        raise RuntimeError("Calibration failed: no fresh power data")
    baseline = statistics.median(calibration[15:])
    if baseline < 15:
        raise RuntimeError(f"Baseline too low ({baseline:.0f} W). Start moving and retry.")
    print(f"Reference: {baseline:.0f} W. Game starting.")
    score = Score()
    rng = random.Random(args.seed)
    events = ["escape"] * 3 + ["defend"] * 3 + ["recover"] * 2
    rng.shuffle(events)
    log = []
    started = time.monotonic()
    await audio.play("ready")
    for number, kind in enumerate(events, 1):
        if not score.lives:
            break
        print(f"Round {number}/8: wait for the sound...", flush=True)
        delay = rng.randint(8, 12)
        if await measure(stream, delay, simulator, "baseline", args.tick) is None:
            raise RuntimeError("Lost power data; stopped without penalty")
        await audio.play(kind)
        print({"escape":"ESCAPE! Accelerate", "defend":"DEFEND! Hold steady", "recover":"RECOVER! Slow down"}[kind], flush=True)
        transition = await measure(stream, 3, simulator, kind, args.tick)
        powers = await measure(stream, 5 if kind == "escape" else 8, simulator, kind, args.tick)
        if transition is None or powers is None:
            raise RuntimeError("Lost power data; stopped without penalty")
        valid, excellent = judge(kind, powers, baseline)
        reward = score.apply(kind, valid, excellent if valid else False)
        await audio.play("success" if valid else "fail")
        if reward["shield_gained"]:
            await audio.play("shield")
        log.append({"round":number, "event":kind, "valid":valid, "excellent":excellent if valid else False,
                    "power_w":[round(p, 1) for p in powers], "earned":reward["earned"],
                    "lives":score.lives, "shield":score.shield, "points":score.points})
        print(f"{'SUCCESS' if valid else 'MISS'} +{reward['earned']} | total={score.points} lives={score.lives} shield={score.shield}", flush=True)
    await audio.play("end")
    output = {"game":"reacciona", "mode":"simulated" if simulator else "PM5", "baseline_w":baseline,
              "real_elapsed_seconds":round(time.monotonic() - started, 1), "score":vars(score), "events":log}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"RESULT: {score.points} points; {score.successes}/{score.attempts} correct; saved {path}")

async def main(args):
    stream = MetricStream()
    audio = Audio(not args.mute)
    try:
        if args.simulate:
            await play_game(args, stream, audio, Simulator(stream, args.simulate_watts, args.seed))
        else:
            def on_metric(metric):
                if metric.kind == "power":
                    stream.update(metric.watts, metric.received_at)
                elif metric.kind == "general":
                    stream.distance = metric.distance_m
            async with PM5Connection(on_metric, args.name):
                print("Connected. Begin calibration.")
                await play_game(args, stream, audio, None)
    finally:
        audio.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="", help="PM5 serial / advertised name")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--simulate-watts", type=float, default=110)
    parser.add_argument("--tick", type=float, default=1, help="Seconds per sample; simulation can use 0")
    parser.add_argument("--mute", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="reacciona-last-session.json")
    args = parser.parse_args()
    try:
        asyncio.run(main(args))
    except (KeyboardInterrupt, RuntimeError) as exc:
        print(f"Stopped: {exc}")
        raise SystemExit(1)
