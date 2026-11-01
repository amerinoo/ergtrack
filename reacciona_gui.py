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
from collections import deque

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
        root.geometry("960x670")
        root.minsize(760, 610)
        root.configure(bg=BG)
        self.messages = queue.Queue()
        self.stop_flag = threading.Event()
        self.running = False
        self.current_bounds = (None, None)
        self.active_kind = "rest"
        self.baseline = 112.0
        self.stream = None
        self.last_watts = None
        self.last_watts_at = 0.0
        self.smoothed_watts = None
        self.last_smoothing_at = 0.0
        self.power_history = deque(maxlen=120)
        self.last_visual_rx = 0.0
        self.started_game = False
        self.phase = "setup"
        self.build()
        root.after(100, self.poll)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def label(self, parent, text, size=14, color=WHITE, bold=False, **kw):
        return tk.Label(parent, text=text, fg=color, bg=parent.cget("bg"), font=("Helvetica", size, "bold" if bold else "normal"), **kw)

    def build(self):
        heading = tk.Frame(self.root, bg=BG)
        heading.pack(fill="x", padx=28, pady=(22, 12))
        self.label(heading, "THE BOX ARCADE", 12, CYAN, True).pack(anchor="w")
        self.label(heading, "REACCIONA", 24, WHITE, True).pack(side="left")
        self.connection = self.label(heading, "● DESCONECTADO", 12, MUTED, True)
        self.connection.pack(side="right", pady=16)

        config = tk.Frame(self.root, bg=PANEL, padx=15, pady=12)
        self.config_panel = config
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

        controls = tk.Frame(self.root, bg=BG)
        self.controls_panel = controls
        controls.pack(side="bottom", fill="x", padx=28, pady=(4, 12))
        self.start_button = self.action_button(controls, "▶  CONECTAR Y PREPARAR", self.start,
                                               CYAN, WHITE)
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.stop_button = self.action_button(controls, "■  DETENER", self.stop,
                                              "#34445B", WHITE, enabled=False)
        self.stop_button.pack(side="left", fill="x", expand=True, padx=(8, 0))

        metrics = tk.Frame(self.root, bg=BG)
        metrics.pack(side="bottom", fill="x", padx=28, pady=6)
        self.points = self.metric(metrics, "PUNTOS", "0", 0)
        self.lives = self.metric(metrics, "VIDAS", "3", 1)
        self.shield = self.metric(metrics, "ESCUDO", "0", 2)
        self.streak = self.metric(metrics, "RACHA", "0", 3)


        panel = tk.Frame(self.root, bg=PANEL, padx=24, pady=16)
        self.game_panel = panel
        panel.pack(fill="both", expand=True, padx=28, pady=5)
        self.round_label = self.label(panel, "PREPARADO · 0/3", 15, MUTED, True)
        self.round_label.pack(pady=(0, 3))
        self.phase_label = self.label(panel, "1. SIÉNTATE EN EL REMO", 22, WHITE, True, wraplength=850)
        self.phase_label.pack(pady=(1, 2))
        self.target = self.label(panel, "2. Pulsa MENU en el PM5 para encenderlo", 14, CYAN, True)
        self.target.pack(pady=(0, 2))
        self.watts = self.label(panel, "— W", 16, MUTED, True)
        self.watts.pack(pady=(0, 2))
        self.feedback = self.label(panel, "3. Pulsa CONECTAR para empezar", 22, WHITE, True, wraplength=840)
        self.feedback.pack(pady=(3, 7))
        self.watts.pack_forget()
        self.gauge = tk.Canvas(panel, height=260, bg="#34445B", highlightthickness=0)
        # Mantener el gauge anterior fuera de la vista: el gráfico histórico es el principal.
        # self.gauge.pack(fill="x", pady=(12, 4))
        self.gauge.bind("<Configure>", lambda _: self.draw_gauge())
        self.gauge_value = None
        self.status = self.label(panel, "Conecta el PM5 y empieza a remar", 14, MUTED, wraplength=660)
        self.status.pack(pady=(2, 5))
        self.history = tk.Canvas(panel, height=340, bg="#172235", highlightthickness=0)
        # No graph until movement/gameplay: keep onboarding clear and compact.
        self.history.bind("<Configure>", lambda _: self.draw_history())


    def action_button(self, parent, title, command, background, foreground, enabled=True):
        """Custom Tk surface: avoids macOS native button colors overriding fg/bg."""
        surface = tk.Frame(parent, bg=background, height=62, cursor="hand2" if enabled else "arrow")
        surface.pack_propagate(False)
        label = tk.Label(surface, text=title, bg=background,
                         fg=foreground if enabled else MUTED,
                         font=("Helvetica", 16, "bold"), cursor="hand2" if enabled else "arrow")
        label.pack(fill="both", expand=True)
        surface._label = label
        surface._command = command
        surface._background = background
        surface._foreground = foreground
        surface._enabled = enabled
        def click(_event):
            if surface._enabled:
                surface._command()
        surface.bind("<Button-1>", click)
        label.bind("<Button-1>", click)
        return surface

    def set_button_enabled(self, button, enabled):
        button._enabled = enabled
        color = button._foreground if enabled else MUTED
        button._label.config(fg=color, cursor="hand2" if enabled else "arrow")
        button.config(cursor="hand2" if enabled else "arrow")

    def metric(self, parent, title, value, col):
        box = tk.Frame(parent, bg=PANEL, pady=10)
        box.grid(row=0, column=col, padx=4, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)
        self.label(box, title, 11, MUTED).pack()
        number = self.label(box, value, 26, WHITE, True)
        number.pack()
        return number

    def draw_gauge(self):
        """Barra azul creciente, con objetivo verde fijo y bien visible."""
        canvas = self.gauge
        canvas.delete("all")
        width = max(80, canvas.winfo_width())
        height = max(160, canvas.winfo_height())
        lo, hi = self.current_bounds
        if lo is None:
            lo, hi = self.baseline * .85, self.baseline * 1.15
        visual_hi = hi if hi is not None else lo * 1.15
        center = (lo + visual_hi) / 2
        half = max(1.0, (visual_hi - lo) / 2)
        # Fixed scale for each goal: the green zone stays near the middle.
        maximum = max(center + 3.2 * half, visual_hi * 1.15)
        minimum = max(0.0, 2 * center - maximum)

        def position(value):
            fraction = (value - minimum) / max(1.0, maximum - minimum)
            return 16 + (width - 32) * max(0.0, min(1.0, fraction))

        top, bottom = 28, height - 42
        left, right = position(lo), position(visual_hi)
        # Background and target corridor always visible, even before rowing.
        canvas.create_rectangle(16, top, width - 16, bottom, fill="#34445B", outline="")
        canvas.create_rectangle(left, top, right, bottom, fill="#29956B", outline="")
        # The blue fill grows from left to right with the smoothed power.
        if self.gauge_value is not None:
            end = position(self.gauge_value)
            if end > 16:
                canvas.create_rectangle(16, top + 10, end, bottom - 10,
                                        fill=CYAN, outline="")
            canvas.create_line(end, top - 7, end, bottom + 7, fill=WHITE, width=4)
        # Target borders remain clear over the blue fill.
        canvas.create_line(left, top - 5, left, bottom + 5, fill=GREEN, width=4)
        if hi is not None:
            canvas.create_line(right, top - 5, right, bottom + 5, fill=GREEN, width=4)
        canvas.create_text(width / 2, height - 16, text="LLEVA EL AZUL HASTA LA ZONA VERDE",
                           fill=GREEN, font=("Helvetica", 12, "bold"))

    def draw_history(self):
        """Trace recent effort against a shaded target corridor."""
        canvas = self.history
        canvas.delete("all")
        w, h = max(80, canvas.winfo_width()), max(60, canvas.winfo_height())
        lo, hi = self.current_bounds
        if lo is None:
            lo, hi = self.baseline * .85, self.baseline * 1.15
        # Zoom vertical relativo al objetivo: franja legible incluso desde el remo.
        visual_hi = hi if hi is not None else lo * 1.25
        midpoint = (lo + visual_hi) / 2
        half_range = max((visual_hi - lo) / 2, 1.0)
        visible_half = half_range * 1.9
        minimum = max(0.0, midpoint - visible_half)
        maximum = midpoint + visible_half
        y = lambda power: h - 12 - max(0, min(1, (power - minimum) / max(1, maximum - minimum))) * (h - 24)
        canvas.create_rectangle(0, y(visual_hi), w, y(lo), fill="#246448", outline="")
        canvas.create_line(0, y(lo), w, y(lo), fill=GREEN, width=2)
        if hi is not None:
            canvas.create_line(0, y(hi), w, y(hi), fill=GREEN, width=2)
        canvas.create_text(9, 8, text="ESFUERZO · ÚLTIMOS 15 S", anchor="nw", fill=MUTED, font=("Helvetica", 9))
        if len(self.power_history) > 1:
            latest = self.power_history[-1][0]
            # The live point stays horizontally centered; older values move left.
            center_x = w / 2
            pixels_per_second = (w / 2 - 12) / 15
            coords = []
            for timestamp, power in self.power_history:
                x = center_x - (latest - timestamp) * pixels_per_second
                if x >= 12:
                    coords.extend((x, y(power)))
            if len(coords) >= 4:
                canvas.create_line(*coords, fill="#07354C", width=29, smooth=True,
                                   capstyle=tk.ROUND, joinstyle=tk.ROUND)
                canvas.create_line(*coords, fill=CYAN, width=20, smooth=True,
                                   capstyle=tk.ROUND, joinstyle=tk.ROUND)
                x, current_y = coords[-2], coords[-1]
                canvas.create_oval(x - 17, current_y - 17, x + 17, current_y + 17,
                                   fill=WHITE, outline=CYAN, width=5)

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
        self.smoothed_watts = None
        self.last_smoothing_at = 0.0
        self.last_visual_rx = 0.0
        self.last_watts = None
        self.phase = "connecting"
        self.feedback.pack_forget()
        self.feedback.pack(pady=(3, 7))
        self.feedback.config(font=("Helvetica", 22, "bold"))
        self.history.pack_forget()
        self.is_simulation = self.simulated.get()
        self.power_history.clear()
        self.running = True
        self.stop_flag.clear()
        self.set_button_enabled(self.start_button, False)
        self.set_button_enabled(self.stop_button, True)
        self.connection.config(text="● SIMULACIÓN" if self.is_simulation else "● CONECTANDO...", fg=GREEN if self.is_simulation else AMBER)
        self.phase_label.config(text="INICIANDO SIMULACIÓN" if self.is_simulation else "CONECTANDO TU REMO", fg=WHITE)
        self.target.config(text="No necesitas una máquina" if self.is_simulation else "Enciende el PM5 pulsando MENU")
        self.feedback.config(text="3. PREPARANDO PARTIDA…" if self.is_simulation else "3. Buscando la máquina…", fg=AMBER)
        self.status.config(text="Generando potencia de prueba…" if self.is_simulation else "No selecciones ningún entrenamiento en el PM5.")
        args = SimpleNamespace(rounds=rounds, baseline=baseline, recalibrate=False,
                               calibration_file=".reacciona-calibration.json", tick=1,
                               output="reacciona-last-session.json", seed=42,
                               name=self.pm5_name.get().strip(), on_event=lambda value: self.messages.put(("event", value)),
                               should_stop=self.stop_flag.is_set)
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
                        self.messages.put(("onboarding", "movement"))
                        while not self.stop_flag.is_set():
                            power = stream.recent_power(time.monotonic())
                            if power is not None and power >= 15:
                                break
                            await asyncio.sleep(.25)
                        if not self.stop_flag.is_set():
                            self.messages.put(("onboarding", "ready"))
                            await asyncio.sleep(2)
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
            self.phase = "playing"
            self.config_panel.pack_forget()
            self.status.pack_forget()
            # First mount the graph: Tkinter cannot use before= on an unpacked widget.
            self.history.pack(fill="both", expand=True, pady=(12, 6))
            self.feedback.pack_forget()
            self.feedback.pack(before=self.target, pady=(3, 7))
            self.feedback.config(font=("Helvetica", 39, "bold"))
            self.watts.pack(pady=(0, 2), before=self.history)
            self.baseline = value["baseline"]
            self.target.config(text="Objetivo de espera: %d–%d W" % (self.baseline*.85, self.baseline*1.15))
        elif event == "rest":
            self.phase = "rest"
            self.active_kind = "rest"
            self.current_bounds = (value["low"], value["high"])
            self.round_label.config(text=f"RONDA {value['round']}/{value['rounds']}")
            self.phase_label.config(text="MANTÉN EL RITMO", fg=MUTED)
            self.target.config(text=f"Objetivo: {value['low']:.0f}–{value['high']:.0f} W")
            self.status.config(text="Mantén este intervalo hasta escuchar la señal")
        elif event == "challenge":
            self.phase = "challenge"
            self.active_kind = value["kind"]
            self.current_bounds = (value["low"], value["high"])
            title = {"escape": "¡ESCAPA!", "defend": "¡DEFIENDE!", "recover": "¡RECUPERA!"}[value["kind"]]
            self.phase_label.config(text=title, fg={"escape": RED, "defend": GREEN, "recover": CYAN}[value["kind"]])
            goal = f"Más de {value['low']:.0f} W" if value["high"] is None else f"{value['low']:.0f}–{value['high']:.0f} W"
            self.target.config(text="Objetivo: " + goal)
        elif event == "countdown":
            self.phase_label.config(text=f"PREPÁRATE · {value['value']}", fg=AMBER)
        elif event == "evaluating":
            self.phase = "evaluating"
            self.phase_label.config(text="MANTÉN EL ESFUERZO", fg=MUTED)
        elif event == "result":
            self.phase = "result"
            self.points.config(text=str(value["points"]))
            self.lives.config(text=str(value["lives"]))
            self.shield.config(text=str(value["shield"]))
            self.streak.config(text=str(value["streak"]))
            self.phase_label.config(text="RESULTADO", fg=MUTED)
            self.feedback.config(text="¡CONSEGUIDO!" if value["valid"] else "SIGUE INTENTÁNDOLO", fg=GREEN if value["valid"] else RED)
            extras = (" +25 excelencia" if value["excellent"] else "") + (" +50 racha" if value["valid"] and value["streak"] % 3 == 0 else "")
            self.status.config(text=f"{value['hits']}/{value['samples']} muestras correctas · +{value['earned']} puntos" + extras)
        elif event == "finished":
            self.phase = "finished"
            self.phase_label.config(text="FIN DE LA PARTIDA", fg=MUTED)
            self.feedback.config(text=f"¡{value['points']} PUNTOS!", fg=GREEN)
            self.status.pack(pady=(2, 5), before=self.history)
            self.status.config(text=f"{value['points']} puntos · {value['successes']}/{value['attempts']} desafíos superados")

    def poll(self):
        try:
            while True:
                kind, data = self.messages.get_nowait()
                if kind == "event":
                    self.apply_event(data)
                elif kind == "onboarding":
                    self.phase = "movement" if data == "movement" else "ready"
                    self.history.pack_forget()
                    self.phase_label.config(text="¡EMPIEZA A REMAR!" if data == "movement" else "¡TODO LISTO!", fg=GREEN)
                    self.target.config(text="Rema suavemente para comprobar la conexión" if data == "movement" else "La partida empieza ahora")
                    self.feedback.config(text="Detectaremos tu primera remada automáticamente" if data == "movement" else "ESCAPA = fuerte · DEFIENDE = constante · RECUPERA = suave", fg=WHITE)
                elif kind == "connected":
                    self.connection.config(text="● " + data, fg=GREEN)
                elif kind == "error":
                    self.status.config(text="Error: " + data)
                    if not self.status.winfo_manager():
                        self.status.pack(pady=(2, 5), before=self.history)
                    self.connection.config(text="● ERROR", fg=RED)
                elif kind == "done":
                    if self.phase not in ("finished", "error"):
                        self.phase = "setup"
                    self.config_panel.pack(fill="x", padx=28, pady=(0, 12), before=self.game_panel)
                    if self.phase == "setup":
                        self.history.pack_forget()
                        self.watts.pack_forget()
                    self.running = False
                    self.set_button_enabled(self.start_button, True)
                    self.set_button_enabled(self.stop_button, False)
        except queue.Empty:
            pass
        if self.stream is not None and self.running:
            now = time.monotonic()
            # The simulator uses virtual time. Convert reception to UI wall time,
            # rather than comparing timestamps from different clock domains.
            newest = self.stream.samples[-1] if self.stream.samples else None
            if newest is not None and newest[0] != self.last_smoothing_at:
                self.last_smoothing_at = newest[0]
                self.last_watts = newest[1]
                self.last_visual_rx = now
                if self.smoothed_watts is None:
                    self.smoothed_watts = self.last_watts
                else:
                    self.smoothed_watts += .28 * (self.last_watts - self.smoothed_watts)
                self.power_history.append((now, self.smoothed_watts))
            shown = self.last_watts
            fresh = shown is not None and now - self.last_visual_rx <= 4
            self.gauge_value = self.smoothed_watts
            self.watts.config(text=f"Potencia · {shown:.0f} W" if shown is not None else "Potencia · — W",
                              fg=WHITE if fresh else MUTED)
            lo, hi = self.current_bounds
            if self.phase in ("playing", "rest", "challenge", "evaluating"):
                if shown is None:
                    self.feedback.config(text="EMPIEZA A REMAR", fg=WHITE)
                elif not fresh:
                    self.feedback.config(text="SIGUE REMANDO PARA CONTINUAR", fg=AMBER)
                elif lo is not None and self.smoothed_watts < lo:
                    self.feedback.config(text="¡REMA MÁS FUERTE!", fg=AMBER)
                elif hi is not None and self.smoothed_watts > hi:
                    self.feedback.config(text="¡REMA MÁS SUAVE!", fg=RED)
                else:
                    self.feedback.config(text="¡ASÍ, PERFECTO!", fg=GREEN)
            self.draw_history()
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
