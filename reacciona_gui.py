#!/usr/bin/env python3
"""The Box Arcade — Reacciona: ventana Tkinter local para macOS."""
import asyncio
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from types import SimpleNamespace
from pathlib import Path
import time

from pm5_ble import PM5Connection
from reacciona import Audio, MetricStream, Simulator, play_game, load_baseline

BG = "#101827"
PANEL = "#202D40"
CYAN = "#00A0D3"
WHITE = "#F3F7FF"
MUTED = "#AABBD0"
GREEN = "#54D6A2"
RED = "#FF7188"
AMBER = "#FFC46B"


class ArcadeGUI:
    def __init__(self, root):
        self.root = root
        root.title("The Box Arcade · Reacciona")
        root.geometry("840x730")
        root.minsize(680, 620)
        root.configure(bg=BG)
        self.messages = queue.Queue()
        self.stop_flag = threading.Event()
        self.running = False
        self.current_bounds = (None, None)
        self.active_kind = "rest"
        self.baseline = 112.0
        self.stream = None
        self.build()
        root.after(100, self.poll)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def label(self, parent, text, size=14, color=WHITE, bold=False, **kw):
        return tk.Label(parent, text=text, fg=color, bg=parent.cget("bg"), font=("Helvetica", size, "bold" if bold else "normal"), **kw)

    def build(self):
        heading = tk.Frame(self.root, bg=BG)
        heading.pack(fill="x", padx=28, pady=(22, 12))
        self.label(heading, "THE BOX ARCADE", 12, CYAN, True).pack(anchor="w")
        self.label(heading, "REACCIONA", 30, WHITE, True).pack(side="left")
        self.connection = self.label(heading, "● DESCONECTADO", 12, MUTED, True)
        self.connection.pack(side="right", pady=16)

        config = tk.Frame(self.root, bg=PANEL, padx=15, pady=12)
        config.pack(fill="x", padx=28, pady=(0, 12))
        self.label(config, "Rondas", 11, MUTED).grid(row=0, column=0, sticky="w")
        self.rounds = tk.Spinbox(config, from_=1, to=20, width=5, font=("Helvetica", 15))
        self.rounds.delete(0, "end")
        self.rounds.insert(0, "3")
        self.rounds.grid(row=1, column=0, padx=(0, 20), sticky="w")
        self.label(config, "Referencia (W)", 11, MUTED).grid(row=0, column=1, sticky="w")
        self.baseline_entry = tk.Entry(config, width=9, font=("Helvetica", 15))
        saved = load_baseline(".reacciona-calibration.json")
        self.baseline_entry.insert(0, str(int(saved or 112)))
        self.baseline_entry.grid(row=1, column=1, padx=(0, 20), sticky="w")
        self.label(config, "Filtro PM5 (opcional)", 11, MUTED).grid(row=0, column=2, sticky="w")
        self.pm5_name = tk.Entry(config, width=19, font=("Helvetica", 15))
        self.pm5_name.grid(row=1, column=2, padx=(0, 20), sticky="w")
        self.simulated = tk.BooleanVar(value=False)
        tk.Checkbutton(config, text="Simulación", variable=self.simulated, bg=PANEL, fg=WHITE, selectcolor=BG, activebackground=PANEL, activeforeground=WHITE).grid(row=1, column=3, sticky="w")

        panel = tk.Frame(self.root, bg=PANEL, padx=24, pady=24)
        panel.pack(fill="both", expand=True, padx=28, pady=5)
        self.round_label = self.label(panel, "PREPARADO · 0/3", 15, MUTED, True)
        self.round_label.pack()
        self.phase_label = self.label(panel, "Pulsa Iniciar partida", 31, WHITE, True, wraplength=670)
        self.phase_label.pack(pady=(12, 6))
        self.target = self.label(panel, "Objetivo: —", 21, CYAN, True)
        self.target.pack(pady=(0, 10))
        self.watts = self.label(panel, "— W", 72, WHITE, True)
        self.watts.pack(pady=(0, 3))
        self.feedback = self.label(panel, "Sin datos de potencia", 16, MUTED, True)
        self.feedback.pack()
        self.gauge = tk.Canvas(panel, height=20, bg="#34445B", highlightthickness=0)
        self.gauge.pack(fill="x", pady=(18, 10))
        self.gauge.bind("<Configure>", lambda _: self.draw_gauge())
        self.gauge_value = None
        self.status = self.label(panel, "Conecta el PM5 y empieza a remar", 14, MUTED, wraplength=660)
        self.status.pack(pady=12)

        metrics = tk.Frame(self.root, bg=BG)
        metrics.pack(fill="x", padx=28, pady=12)
        self.points = self.metric(metrics, "PUNTOS", "0", 0)
        self.lives = self.metric(metrics, "VIDAS", "3", 1)
        self.shield = self.metric(metrics, "ESCUDO", "0", 2)
        self.streak = self.metric(metrics, "RACHA", "0", 3)

        controls = tk.Frame(self.root, bg=BG)
        controls.pack(fill="x", padx=28, pady=(0, 18))
        self.start_button = tk.Button(controls, text="▶ Iniciar partida", command=self.start, bg=CYAN, fg="white", font=("Helvetica", 15, "bold"), relief="flat", padx=18, pady=12)
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.stop_button = tk.Button(controls, text="■ Detener", command=self.stop, bg="#34445B", fg="white", font=("Helvetica", 15), relief="flat", padx=18, pady=12, state="disabled")
        self.stop_button.pack(side="left", fill="x", expand=True, padx=(8, 0))

    def metric(self, parent, title, value, col):
        box = tk.Frame(parent, bg=PANEL, pady=10)
        box.grid(row=0, column=col, padx=4, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)
        self.label(box, title, 11, MUTED).pack()
        number = self.label(box, value, 26, WHITE, True)
        number.pack()
        return number

    def draw_gauge(self):
        self.gauge.delete("all")
        width = max(1, self.gauge.winfo_width())
        if self.gauge_value is None:
            return
        fill = max(0, min(1, self.gauge_value / max(300, self.baseline * 2.5)))
        self.gauge.create_rectangle(0, 0, width * fill, 20, fill=CYAN, outline="")

    def start(self):
        if self.running:
            return
        try:
            rounds = int(self.rounds.get())
            baseline = float(self.baseline_entry.get())
            if not 1 <= rounds <= 20 or not 15 <= baseline <= 3000:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Configuración incorrecta", "Rondas: 1-20. Referencia: 15-3000 W.")
            return
        self.baseline = baseline
        self.running = True
        self.stop_flag.clear()
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.connection.config(text="● CONECTANDO...", fg=AMBER)
        self.status.config(text="Buscando PM5 por Bluetooth…" if not self.simulated.get() else "Preparando simulación…")
        args = SimpleNamespace(rounds=rounds, baseline=baseline, recalibrate=False,
                               calibration_file=".reacciona-calibration.json", tick=1,
                               output="reacciona-last-session.json", seed=42,
                               name=self.pm5_name.get().strip(), on_event=lambda value: self.messages.put(("event", value)))
        threading.Thread(target=self.worker, args=(args, self.simulated.get()), daemon=True).start()

    def worker(self, args, simulated):
        async def work():
            stream = MetricStream()
            self.stream = stream
            audio = Audio()
            try:
                if simulated:
                    self.messages.put(("connected", "SIMULACIÓN"))
                    simulator = Simulator(stream, args.baseline, args.seed)
                    await play_game(args, stream, audio, simulator)
                else:
                    def metric_received(metric):
                        if metric.kind == "power":
                            stream.update(metric.watts, metric.received_at)
                        elif metric.kind == "general":
                            stream.distance = metric.distance_m
                    async with PM5Connection(metric_received, args.name, interactive=False):
                        self.messages.put(("connected", "PM5 CONECTADO"))
                        if not self.stop_flag.is_set():
                            await play_game(args, stream, audio, None)
            finally:
                audio.close()
        try:
            asyncio.run(work())
        except Exception as exc:
            self.messages.put(("error", str(exc)))
        finally:
            self.messages.put(("done", None))

    def apply_event(self, value):
        event = value["event"]
        if event == "start":
            self.baseline = value["baseline"]
            self.target.config(text="Objetivo de espera: %d–%d W" % (self.baseline*.85, self.baseline*1.15))
        elif event == "rest":
            self.active_kind = "rest"
            self.current_bounds = (value["low"], value["high"])
            self.round_label.config(text=f"RONDA {value['round']}/{value['rounds']}")
            self.phase_label.config(text="REMA A RITMO CÓMODO", fg=WHITE)
            self.target.config(text=f"Objetivo: {value['low']:.0f}–{value['high']:.0f} W")
            self.status.config(text="Mantén este intervalo hasta escuchar la señal")
        elif event == "challenge":
            self.active_kind = value["kind"]
            self.current_bounds = (value["low"], value["high"])
            title = {"escape": "¡ESCAPA!", "defend": "¡DEFIENDE!", "recover": "¡RECUPERA!"}[value["kind"]]
            self.phase_label.config(text=title, fg={"escape": RED, "defend": GREEN, "recover": CYAN}[value["kind"]])
            goal = f"Más de {value['low']:.0f} W" if value["high"] is None else f"{value['low']:.0f}–{value['high']:.0f} W"
            self.target.config(text="Objetivo: " + goal)
        elif event == "countdown":
            self.status.config(text=f"CAMBIA DE RITMO · {value['value']}")
        elif event == "evaluating":
            self.status.config(text=f"Evaluando durante {value['seconds']} muestras…")
        elif event == "result":
            self.points.config(text=str(value["points"]))
            self.lives.config(text=str(value["lives"]))
            self.shield.config(text=str(value["shield"]))
            self.streak.config(text=str(value["streak"]))
            self.phase_label.config(text="¡ACIERTO!" if value["valid"] else "NO CONSEGUIDO", fg=GREEN if value["valid"] else RED)
            extras = (" +25 excelencia" if value["excellent"] else "") + (" +50 racha" if value["valid"] and value["streak"] % 3 == 0 else "")
            self.status.config(text=f"{value['hits']}/{value['samples']} muestras correctas · +{value['earned']} puntos" + extras)
        elif event == "finished":
            self.phase_label.config(text="PARTIDA TERMINADA", fg=GREEN)
            self.status.config(text=f"{value['points']} puntos · {value['successes']}/{value['attempts']} desafíos superados")

    def poll(self):
        try:
            while True:
                kind, data = self.messages.get_nowait()
                if kind == "event":
                    self.apply_event(data)
                elif kind == "connected":
                    self.connection.config(text="● " + data, fg=GREEN)
                elif kind == "error":
                    self.status.config(text="Error: " + data)
                    self.connection.config(text="● ERROR", fg=RED)
                elif kind == "done":
                    self.running = False
                    self.start_button.config(state="normal")
                    self.stop_button.config(state="disabled")
        except queue.Empty:
            pass
        if self.stream is not None and self.running:
            watts = self.stream.recent_power(time.monotonic())
            self.gauge_value = watts
            self.watts.config(text=f"{watts:.0f} W" if watts is not None else "— W")
            lo, hi = self.current_bounds
            if watts is None:
                self.feedback.config(text="Esperando potencia", fg=MUTED)
            elif lo is not None:
                if watts < lo:
                    self.feedback.config(text="Por debajo del objetivo", fg=AMBER)
                elif hi is not None and watts > hi:
                    self.feedback.config(text="Por encima del objetivo", fg=RED)
                else:
                    self.feedback.config(text="Dentro del objetivo", fg=GREEN)
            self.draw_gauge()
        self.root.after(100, self.poll)

    def stop(self):
        if self.running:
            self.stop_flag.set()
            self.status.config(text="Deteniendo al terminar la fase actual…")
            self.stop_button.config(state="disabled")

    def close(self):
        self.stop_flag.set()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    ArcadeGUI(root)
    root.mainloop()
