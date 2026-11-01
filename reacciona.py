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
        "countdown": [(620, .12)],
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

    async def speak(self, message):
        return  # Voz desactivada; mantener señales sonoras.
        if not self.enabled:
            return
        try:
            process = await asyncio.create_subprocess_exec('say', '-v', 'Monica', '-r', '190', message)
            await process.wait()
        except FileNotFoundError:
            print('Voz de macOS no disponible.', flush=True)

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
    """Evaluate active effort, waiting for valid samples instead of failing on one gap."""
    readings = []
    for _ in range(count):
        if simulator:
            await simulator.tick(target)
            await asyncio.sleep(interval if interval else 0)
            power = stream.recent_power(simulator.virtual_time)
        else:
            deadline = time.monotonic() + 12
            power = None
            while time.monotonic() < deadline:
                await asyncio.sleep(interval)
                power = stream.recent_power(time.monotonic())
                if power is not None:
                    break
            if power is None:
                print("No llegan datos de potencia durante el desafío; se detiene sin penalización.", flush=True)
                return None
        if power is None:
            return None
        readings.append(power)
    return readings

async def rest_phase(seconds, simulator, stream, interval):
    """Rest does not require fresh power samples; no false disconnect on inactivity."""
    if simulator:
        for _ in range(seconds):
            await simulator.tick("baseline")
            await asyncio.sleep(interval if interval else 0)
    else:
        await asyncio.sleep(seconds)

async def calibrate(stream, simulator, interval, wait_timeout=90):
    """Wait for actual movement before starting the calibration clock."""
    print("Preparado. Empieza a remar a ritmo cómodo para iniciar la calibración.", flush=True)
    if simulator:
        await simulator.tick("baseline")
    else:
        deadline = time.monotonic() + wait_timeout
        while time.monotonic() < deadline:
            power = stream.recent_power(time.monotonic())
            if power is not None and power >= 15:
                break
            await asyncio.sleep(0.25)
        else:
            raise RuntimeError("No rowing detected within 90 seconds. Check the PM5 and retry.")
    readings = []
    # A few missed notifications must not abort the entire calibration.
    maximum_ticks = 60
    for index in range(maximum_ticks):
        if simulator:
            await simulator.tick("baseline")
            await asyncio.sleep(interval if interval else 0)
            now = simulator.virtual_time
        else:
            await asyncio.sleep(interval)
            now = time.monotonic()
        power = stream.recent_power(now)
        if power is not None and power >= 15:
            readings.append(power)
        if len(readings) >= 45:
            return statistics.median(readings[15:])
        if (index + 1) % 15 == 0:
            print(f"Calibración: {len(readings)}/45 muestras válidas", flush=True)
    raise RuntimeError(f"Calibration incomplete: {len(readings)}/45 valid samples. Check movement and BLE updates.")

def valid_baseline(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 15 <= value <= 3000


def load_baseline(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        value = data["baseline_w"]
        return float(value) if valid_baseline(value) else None
    except (OSError, ValueError, TypeError, KeyError):
        return None


def save_baseline(path, baseline):
    if not valid_baseline(baseline):
        raise ValueError("Invalid baseline power")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({"baseline_w": round(baseline, 2)}, indent=2) + "\n", encoding="utf-8")


async def resolve_baseline(args, stream, simulator):
    if args.baseline is not None:
        print(f"Usando referencia manual: {args.baseline:.0f} W.", flush=True)
        return args.baseline
    if not args.recalibrate and not simulator:
        saved = load_baseline(args.calibration_file)
        if saved is not None:
            print(f"Reutilizando referencia guardada: {saved:.0f} W. Usa --recalibrate para medir de nuevo.", flush=True)
            return saved
    print("CALIBRACIÓN: mantén un esfuerzo cómodo durante 45 muestras válidas.", flush=True)
    baseline = await calibrate(stream, simulator, args.tick)
    if not simulator:
        save_baseline(args.calibration_file, baseline)
        print(f"Referencia guardada en {args.calibration_file}.", flush=True)
    return baseline


async def play_game(args, stream, audio, simulator):
    baseline = await resolve_baseline(args, stream, simulator)
    if baseline < 15:
        raise RuntimeError(f"Baseline too low ({baseline:.0f} W). Start moving and retry.")
    print(f"Referencia: {baseline:.0f} W. Empieza el juego.")
    print(f"Entre desafíos: mantén {baseline*.85:.0f}-{baseline*1.15:.0f} W, sin dejar de remar.")
    print("REGLAS: +100 por acierto; +25 si el 90% de muestras cumple el objetivo; +50 cada 3 aciertos seguidos.")
    print("ESCAPAR: al menos 130% de referencia (4/5 lecturas); DEFENDER: 85%-115%; RECUPERAR: 45%-75% (6/8 lecturas).")
    print("Tres vidas; fallar ESCAPAR quita una vida; dos DEFENDER correctos dan un escudo.")
    await audio.speak("Bienvenido a Reacciona. Entre desafíos sigue remando a ritmo cómodo. Escapar significa remar fuerte, defender significa mantener tu ritmo y recuperar significa remar suave. Después de cada aviso tendrás tres segundos para cambiar el esfuerzo.")
    score = Score()
    rng = random.Random(args.seed)
    events = [rng.choice(["escape", "defend", "recover"]) for _ in range(args.rounds)]
    for i in range(1, len(events)):
        if events[i] == "escape" and events[i - 1] == "escape":
            events[i] = rng.choice(["defend", "recover"])
    log = []
    started = time.monotonic()
    await audio.play("ready")
    for number, kind in enumerate(events, 1):
        if not score.lives:
            break
        print(f"Ronda {number}/{args.rounds}: mantén {baseline*.85:.0f}-{baseline*1.15:.0f} W y espera la señal.", flush=True)
        delay = rng.randint(8, 12)
        await rest_phase(delay, simulator, stream, args.tick)
        instructions = {
            "escape": f"¡Escapa! Rema fuerte, supera {baseline*1.30:.0f} vatios.",
            "defend": f"¡Defiende! Mantén entre {baseline*.85:.0f} y {baseline*1.15:.0f} vatios.",
            "recover": f"¡Recupera! Rema suave entre {baseline*.45:.0f} y {baseline*.75:.0f} vatios.",
        }
        print(instructions[kind], flush=True)
        await audio.play(kind)
        await audio.speak(instructions[kind])
        print("Cuenta atrás: ", end="", flush=True)
        transition = []
        for remaining in (3, 2, 1):
            print(f"{remaining}... ", end="", flush=True)
            await audio.play("countdown")
            sample = await measure(stream, 1, simulator, kind, args.tick)
            if sample is None:
                transition = None
                break
            transition.extend(sample)
        print("¡YA!", flush=True)
        await audio.play("ready")
        print("Evaluando...", flush=True)
        powers = await measure(stream, 5 if kind == "escape" else 8, simulator, kind, args.tick)
        if transition is None or powers is None:
            raise RuntimeError("No llegan datos de potencia del PM5 durante el desafío. Sin penalización.")
        valid, excellent = judge(kind, powers, baseline)
        reward = score.apply(kind, valid, excellent if valid else False)
        if valid:
            bonus = []
            if excellent:
                bonus.append("+25 excelencia")
            if score.streak % 3 == 0:
                bonus.append("+50 racha")
            print("Puntos: +100 acierto" + (" " + " ".join(bonus) if bonus else "") + f" = +{reward['earned']}.", flush=True)
        await audio.play("success" if valid else "fail")
        lo, hi = {"escape": (baseline * 1.30, None), "defend": (baseline * .85, baseline * 1.15), "recover": (baseline * .45, baseline * .75)}[kind]
        hits = sum(p >= lo if hi is None else lo <= p <= hi for p in powers)
        goal = f"mínimo {lo:.0f} W" if hi is None else f"{lo:.0f}-{hi:.0f} W"
        print(f"Resultado: {hits}/{len(powers)} muestras dentro del objetivo ({goal}); media {statistics.mean(powers):.0f} W.", flush=True)
        await audio.speak("¡Conseguido! Ganas puntos. Vuelve al ritmo cómodo." if valid else "No conseguido. Vuelve al ritmo cómodo para la próxima ronda.")
        if reward["shield_gained"]:
            await audio.play("shield")
        log.append({"round":number, "event":kind, "valid":valid, "excellent":excellent if valid else False,
                    "power_w":[round(p, 1) for p in powers], "earned":reward["earned"],
                    "lives":score.lives, "shield":score.shield, "points":score.points})
        print(f"{'ACIERTO' if valid else 'FALLO'} +{reward['earned']} | total={score.points} vidas={score.lives} escudo={score.shield}", flush=True)
    await audio.play("end")
    output = {"game":"reacciona", "mode":"simulated" if simulator else "PM5", "baseline_w":baseline,
              "real_elapsed_seconds":round(time.monotonic() - started, 1), "score":vars(score), "events":log}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"RESULTADO: {score.points} puntos; {score.successes}/{score.attempts} aciertos; guardado en {path}")

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
                print("Conectado. Preparando partida.")
                await play_game(args, stream, audio, None)
    finally:
        audio.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="", help="PM5 serial / advertised name")
    parser.add_argument("--baseline", type=float, help="Override calibration with a manual power reference in W")
    parser.add_argument("--recalibrate", action="store_true", help="Ignore saved reference and recalibrate")
    parser.add_argument("--calibration-file", default=".reacciona-calibration.json", help="Path to locally saved reference")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--simulate-watts", type=float, default=110)
    parser.add_argument("--tick", type=float, default=1, help="Seconds per sample; simulation can use 0")
    parser.add_argument("--mute", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rounds", type=int, default=3, help="Número de rondas, entre 1 y 20")
    parser.add_argument("--output", default="reacciona-last-session.json")
    args = parser.parse_args()
    if not 1 <= args.rounds <= 20:
        parser.error("--rounds debe estar entre 1 y 20")
    if args.baseline is not None and not valid_baseline(args.baseline):
        parser.error("--baseline must be between 15 and 3000 W")
    if args.baseline is not None and args.recalibrate:
        parser.error("--baseline and --recalibrate cannot be combined")
    try:
        asyncio.run(main(args))
    except (KeyboardInterrupt, RuntimeError) as exc:
        print(f"Juego detenido: {exc}")
        raise SystemExit(1)
