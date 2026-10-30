"""Consola de escritorio de Espectro."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

from pyaudio_app.auth import first_run_hint
from pyaudio_app.brand import COMPANY, PRODUCT, STEPS, TAGLINE, WINDOW_TITLE
from pyaudio_app.station import Station
from pyaudio_app.storage import Take, list_takes

BG = "#0e141b"
PANEL = "#17212b"
INK = "#e8eef5"
MUTED = "#8ea0b5"
LINE = "#2c3d4e"
TX = "#f0a202"
RX = "#2ec4b6"
STOP = "#e85d4c"
FONT = "Segoe UI"
MONO = "Consolas"


class App:
    def __init__(self, root: tk.Tk, station: Station | None = None, web_url: str | None = None) -> None:
        self.root = root
        self.station = station or Station()
        self.web_url = web_url
        self.alive = True
        self.screen = "login"
        self._takes: dict[str, Take] = {}
        self._revision = -1
        self._last_error = ""
        self._apply_theme()
        self.container = ttk.Frame(root, padding=18)
        self.container.pack(fill="both", expand=True)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._show_login()

    def _apply_theme(self) -> None:
        self.root.configure(bg=BG)
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=INK, font=(FONT, 10))
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=INK, font=(FONT, 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=INK, font=(FONT, 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=(FONT, 10))
        style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED, font=(FONT, 9))
        style.configure("Company.TLabel", background=BG, foreground=TX, font=(FONT, 10, "bold"))
        style.configure("Header.TLabel", background=BG, foreground=INK, font=(FONT, 26, "bold"))
        style.configure("Tx.TLabel", background=PANEL, foreground=TX, font=(FONT, 12, "bold"))
        style.configure("Rx.TLabel", background=PANEL, foreground=RX, font=(FONT, 12, "bold"))
        style.configure("Level.TLabel", background=PANEL, foreground=INK, font=(MONO, 18, "bold"))
        style.configure("Status.TLabel", background=BG, foreground=INK, font=(FONT, 12, "bold"))
        style.configure("TLabelframe", background=BG, foreground=MUTED, bordercolor=LINE)
        style.configure("TLabelframe.Label", background=BG, foreground=MUTED, font=(FONT, 10, "bold"))
        style.configure("TButton", padding=(12, 7), font=(FONT, 10), background="#243444", foreground=INK)
        style.map("TButton", background=[("active", "#314658"), ("disabled", "#1a2530")])
        style.configure("Accent.TButton", padding=(14, 8), background=TX, foreground="#1a1203", font=(FONT, 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#ffb703"), ("disabled", "#6d5a2a")])
        style.configure("Stop.TButton", padding=(14, 8), background=STOP, foreground="white", font=(FONT, 10, "bold"))
        style.map("Stop.TButton", background=[("active", "#ff6b5a"), ("disabled", "#5a3330")])
        style.configure("TEntry", fieldbackground="#0c1218", foreground=INK, padding=6)
        style.configure("TSpinbox", fieldbackground="#0c1218", foreground=INK, arrowsize=12)
        style.configure("TCombobox", fieldbackground="#0c1218", foreground=INK, padding=4)
        style.map("TCombobox", fieldbackground=[("readonly", "#0c1218")], foreground=[("readonly", INK)])
        style.configure(
            "Treeview",
            background=PANEL,
            fieldbackground=PANEL,
            foreground=INK,
            bordercolor=LINE,
            rowheight=28,
            font=(FONT, 10),
        )
        style.configure("Treeview.Heading", background="#121a22", foreground=MUTED, font=(FONT, 10, "bold"))
        style.map("Treeview", background=[("selected", "#243444")], foreground=[("selected", INK)])

    def _clear(self) -> None:
        for child in self.container.winfo_children():
            child.destroy()

    def _show_login(self) -> None:
        self.screen = "login"
        self._clear()
        self.root.title(WINDOW_TITLE)
        self.root.geometry("560x520")
        self.root.minsize(520, 480)
        self.root.resizable(False, False)
        card = ttk.Frame(self.container)
        card.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(card, text=COMPANY.upper(), style="Company.TLabel").pack(anchor="w")
        ttk.Label(card, text=PRODUCT, style="Header.TLabel").pack(anchor="w", pady=(2, 6))
        ttk.Label(card, text=TAGLINE, style="Muted.TLabel", wraplength=460, justify="left").pack(anchor="w", pady=(0, 16))

        form = ttk.Frame(card)
        form.pack(fill="x")
        ttk.Label(form, text="Usuario").grid(row=0, column=0, sticky="w", pady=6)
        self.username = ttk.Entry(form, width=32)
        self.username.grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=6)
        ttk.Label(form, text="Contraseña").grid(row=1, column=0, sticky="w", pady=6)
        self.password = ttk.Entry(form, width=32, show="*")
        self.password.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=6)
        form.columnconfigure(1, weight=1)

        self.login_status = ttk.Label(card, text="", style="Muted.TLabel")
        self.login_status.pack(anchor="w", pady=(8, 8))
        ttk.Button(card, text="Entrar a la estación", style="Accent.TButton", command=self._login).pack(anchor="w")
        ttk.Label(
            card,
            text=first_run_hint(),
            wraplength=460,
            justify="left",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(16, 0))
        self.username.focus_set()
        self.root.bind("<Return>", lambda _event: self._login())

    def _login(self) -> None:
        username = self.username.get()
        password = self.password.get()
        if not username.strip() or not password:
            self.login_status.configure(text="Ingresa usuario y contraseña.")
            return
        if not self.station.users.authenticate(username, password):
            self.login_status.configure(text="Acceso denegado. Revisa los datos.")
            return
        self.root.unbind("<Return>")
        self._show_main()

    def _show_main(self) -> None:
        self.screen = "main"
        self._clear()
        self._revision = -1
        self.root.title(WINDOW_TITLE)
        self.root.geometry("1080x800")
        self.root.minsize(960, 720)
        self.root.resizable(True, True)

        header = ttk.Frame(self.container)
        header.pack(fill="x")
        titles = ttk.Frame(header)
        titles.pack(side="left", fill="x", expand=True)
        ttk.Label(titles, text=COMPANY.upper(), style="Company.TLabel").pack(anchor="w")
        ttk.Label(titles, text=PRODUCT, style="Header.TLabel").pack(anchor="w")
        actions = ttk.Frame(header)
        actions.pack(side="right")
        web_state = "normal" if self.web_url else "disabled"
        ttk.Button(actions, text="Consola web", command=self._open_web, state=web_state).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Salir", command=self._logout).pack(side="left")
        ttk.Label(self.container, text=TAGLINE, style="Muted.TLabel", wraplength=980).pack(anchor="w", pady=(4, 8))
        steps = ttk.Frame(self.container)
        steps.pack(fill="x", pady=(0, 12))
        for index, step in enumerate(STEPS, start=1):
            ttk.Label(steps, text=f"{index}. {step}", style="Muted.TLabel", wraplength=320, justify="left").grid(
                row=0, column=index - 1, sticky="nw", padx=(0, 16)
            )
        steps.columnconfigure(0, weight=1)
        steps.columnconfigure(1, weight=1)
        steps.columnconfigure(2, weight=1)

        desk = ttk.Frame(self.container, style="Panel.TFrame", padding=16)
        desk.pack(fill="x")
        lamp_row = ttk.Frame(desk, style="Panel.TFrame")
        lamp_row.pack(fill="x")
        self.lamp = tk.Canvas(lamp_row, width=16, height=16, bg=PANEL, highlightthickness=0)
        self.lamp.pack(side="left", padx=(0, 8))
        self.mode_label = ttk.Label(lamp_row, text="EN ESPERA", style="Panel.TLabel")
        self.mode_label.pack(side="left")
        self.status = ttk.Label(desk, text="", style="PanelMuted.TLabel")
        self.status.pack(anchor="w", pady=(6, 12))

        meters = ttk.Frame(desk, style="Panel.TFrame")
        meters.pack(fill="x")
        self.tx_canvas, self.tx_value = self._meter(meters, "Envío", "Canal izquierdo · sale del transmisor", "Tx.TLabel")
        self.rx_canvas, self.rx_value = self._meter(meters, "Recepción", "Canal derecho · vuelve a la estación", "Rx.TLabel")
        meters.columnconfigure(0, weight=1)
        meters.columnconfigure(1, weight=1)

        ttk.Label(desk, text="Espectro del mensaje", style="PanelMuted.TLabel").pack(anchor="w", pady=(14, 4))
        self.spectrum = tk.Canvas(desk, height=110, bg="#0c1218", highlightthickness=0)
        self.spectrum.pack(fill="x")
        self.spectrum.bind("<Configure>", lambda _event: self._paint(self.station.snapshot()))

        form = ttk.LabelFrame(self.container, text="Transmisor", padding=12)
        form.pack(fill="x", pady=(14, 0))
        ttk.Label(form, text="Micrófono").grid(row=0, column=0, sticky="w")
        self.device = ttk.Combobox(form, state="readonly", width=62)
        self.device.grid(row=0, column=1, columnspan=5, sticky="ew", padx=8)
        ttk.Button(form, text="Actualizar", command=self._load_devices).grid(row=0, column=6)
        ttk.Label(form, text="Duración (s)").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.duration = ttk.Spinbox(form, from_=1, to=300, width=8)
        _set_entry(self.duration, "10")
        self.duration.grid(row=1, column=1, sticky="w", padx=8, pady=(10, 0))
        ttk.Label(form, text="Umbral").grid(row=1, column=2, sticky="e", pady=(10, 0))
        self.threshold = ttk.Spinbox(form, from_=1, to=1000, width=8)
        _set_entry(self.threshold, "20")
        self.threshold.grid(row=1, column=3, sticky="w", padx=8, pady=(10, 0))
        ttk.Label(form, text="Silencio (s)").grid(row=1, column=4, sticky="e", pady=(10, 0))
        self.silence = ttk.Spinbox(form, from_=1, to=30, width=8)
        _set_entry(self.silence, "3")
        self.silence.grid(row=1, column=5, sticky="w", padx=8, pady=(10, 0))
        form.columnconfigure(1, weight=1)

        controls = ttk.Frame(self.container)
        controls.pack(fill="x", pady=(12, 0))
        self.record_button = ttk.Button(controls, text="Grabar espectro", style="Accent.TButton", command=self._record)
        self.record_button.pack(side="left")
        self.listen_button = ttk.Button(controls, text="Escuchar transmisor", command=self._toggle_listen)
        self.listen_button.pack(side="left", padx=8)
        self.stop_button = ttk.Button(controls, text="Detener", style="Stop.TButton", command=self._stop, state="disabled")
        self.stop_button.pack(side="left")
        ttk.Label(
            controls,
            text="El umbral reacciona si habla el envío o la recepción.",
            style="Muted.TLabel",
        ).pack(side="left", padx=12)

        library = ttk.LabelFrame(self.container, text="Mensajes guardados", padding=12)
        library.pack(fill="both", expand=True, pady=(14, 0))
        columns = ("fecha", "duracion", "tipo", "archivo")
        self.library = ttk.Treeview(library, columns=columns, show="headings", selectmode="browse")
        self.library.heading("fecha", text="Fecha")
        self.library.heading("duracion", text="Duración")
        self.library.heading("tipo", text="Tipo")
        self.library.heading("archivo", text="Archivo")
        self.library.column("fecha", width=160, anchor="w")
        self.library.column("duracion", width=90, anchor="center")
        self.library.column("tipo", width=100, anchor="center")
        self.library.column("archivo", width=320, anchor="w")
        self.library.pack(fill="both", expand=True)
        self.library.bind("<Double-1>", lambda _event: self._play("primary"))

        library_actions = ttk.Frame(library)
        library_actions.pack(fill="x", pady=(8, 0))
        ttk.Button(library_actions, text="Espectro", command=lambda: self._play("primary")).pack(side="left")
        ttk.Button(library_actions, text="Envío", command=lambda: self._play("envio")).pack(side="left", padx=8)
        ttk.Button(library_actions, text="Recepción", command=lambda: self._play("recepcion")).pack(side="left")
        ttk.Button(library_actions, text="Abrir carpeta", command=self._open_folder).pack(side="left", padx=8)
        ttk.Button(library_actions, text="Recargar", command=self._reload_takes).pack(side="left")

        self._device_by_label: dict[str, int] = {}
        self._load_devices()
        self._reload_takes()
        self._tick()

    def _meter(self, parent: ttk.Frame, title: str, hint: str, style: str) -> tuple[tk.Canvas, ttk.Label]:
        column = 0 if title == "Envío" else 1
        block = ttk.Frame(parent, style="Panel.TFrame")
        block.grid(row=0, column=column, sticky="nsew", padx=(0, 18) if column == 0 else (18, 0))
        ttk.Label(block, text=title, style=style).pack(anchor="w")
        ttk.Label(block, text=hint, style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 6))
        canvas = tk.Canvas(block, height=22, bg="#0c1218", highlightthickness=0)
        canvas.pack(fill="x")
        value = ttk.Label(block, text="0", style="Level.TLabel")
        value.pack(anchor="w", pady=(4, 0))
        return canvas, value

    def _logout(self) -> None:
        if self.station.engine.busy:
            self.station.stop()
        self._show_login()

    def _open_web(self) -> None:
        if self.web_url:
            webbrowser.open(self.web_url)

    def _load_devices(self) -> None:
        try:
            devices = self.station.list_inputs()
        except Exception as exc:
            self._set_status(f"No se pudieron leer los micrófonos: {exc}")
            return
        self._device_by_label = {}
        labels: list[str] = []
        for index, name in devices:
            label = name if name not in self._device_by_label else f"{name} ({index})"
            self._device_by_label[label] = index
            labels.append(label)
        self.device["values"] = labels
        if labels:
            self.device.current(0)
        else:
            self._set_status("No hay micrófonos disponibles.")

    def _record(self) -> None:
        seconds = _read_number(self.duration.get(), minimum=1, maximum=300)
        if seconds is None:
            self._set_status("La duración debe estar entre 1 y 300 segundos.")
            return
        error = self.station.record(self._selected_device(), seconds)
        if error:
            self._fail(error)

    def _toggle_listen(self) -> None:
        if self.station.snapshot()["mode"] == "threshold":
            self._stop()
            return
        threshold = _read_number(self.threshold.get(), minimum=1, maximum=1000)
        silence = _read_number(self.silence.get(), minimum=1, maximum=30)
        if threshold is None or silence is None:
            self._set_status("Revisa el umbral (1-1000) y el silencio (1-30 s).")
            return
        error = self.station.listen(self._selected_device(), threshold, silence)
        if error:
            self._fail(error)

    def _stop(self) -> None:
        self.stop_button.configure(state="disabled")
        self._set_status("Deteniendo...")
        self.station.stop()

    def _play(self, part: str) -> None:
        take = self._selected_take()
        if take is None:
            self._set_status("Elige un mensaje.")
            return
        path = _part_path(take, part)
        if path is None:
            self._set_status("Ese canal no está en esta toma.")
            return
        error = self.station.play(path)
        if error:
            self._fail(error)

    def _open_folder(self) -> None:
        take = self._selected_take()
        folder = take.primary.parent if take and take.primary else self.station.recordings_dir
        folder.mkdir(parents=True, exist_ok=True)
        _open_path(folder)

    def _reload_takes(self) -> None:
        if not hasattr(self, "library") or not self.library.winfo_exists():
            return
        selected = self.library.selection()
        previous = self._takes.get(selected[0]).name if selected and selected[0] in self._takes else None
        for item in self.library.get_children():
            self.library.delete(item)
        self._takes = {}
        for index, take in enumerate(list_takes(self.station.recordings_dir)):
            iid = f"take-{index}"
            self._takes[iid] = take
            self.library.insert(
                "",
                "end",
                iid=iid,
                values=(
                    take.modified.strftime("%Y-%m-%d %H:%M:%S"),
                    f"{take.seconds:.1f} s",
                    take.kind,
                    take.name,
                ),
            )
        for iid, take in self._takes.items():
            if take.name == previous:
                self.library.selection_set(iid)
                break

    def _selected_device(self) -> int | None:
        label = self.device.get()
        if not label:
            return None
        return self._device_by_label.get(label)

    def _selected_take(self) -> Take | None:
        selection = self.library.selection()
        if not selection:
            return None
        take = self._takes.get(selection[0])
        if take is None or take.primary is None or not take.primary.exists():
            self._set_status("Ese mensaje ya no está en disco.")
            self._reload_takes()
            return None
        return take

    def _tick(self) -> None:
        if not self.alive or self.screen != "main":
            return
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return
        snap = self.station.snapshot()
        self._paint(snap)
        revision = int(snap["revision"])
        if revision != self._revision:
            self._revision = revision
            self._reload_takes()
        error = str(snap["error"])
        if error and error != self._last_error:
            self._last_error = error
            messagebox.showerror(PRODUCT, error, parent=self.root)
        elif not error:
            self._last_error = ""
        self.root.after(100, self._tick)

    def _paint(self, snap: dict[str, object]) -> None:
        if self.screen != "main" or not hasattr(self, "spectrum"):
            return
        mode = str(snap["mode"])
        envio = float(snap["envio"])
        recepcion = float(snap["recepcion"])
        bands = [float(item) for item in snap["bands"]]  # type: ignore[union-attr]
        self._set_status(str(snap["status"]))
        self.tx_value.configure(text=str(min(999, int(round(envio)))))
        self.rx_value.configure(text=str(min(999, int(round(recepcion)))))
        _draw_bar(self.tx_canvas, envio, TX)
        _draw_bar(self.rx_canvas, recepcion, RX)
        _draw_spectrum(self.spectrum, bands)
        _draw_lamp(self.lamp, mode)
        labels = {"idle": "EN ESPERA", "timed": "GRABANDO", "threshold": "ESCUCHANDO"}
        self.mode_label.configure(text=labels.get(mode, "EN ESPERA"))
        busy = bool(snap["busy"])
        self.record_button.configure(state="disabled" if busy else "normal")
        self.stop_button.configure(state="normal" if busy else "disabled")
        if mode == "threshold":
            self.listen_button.configure(text="Dejar de escuchar", state="normal")
        else:
            self.listen_button.configure(text="Escuchar transmisor", state="disabled" if busy else "normal")

    def _set_status(self, text: str) -> None:
        if hasattr(self, "status") and self.status.winfo_exists():
            self.status.configure(text=text)

    def _fail(self, text: str) -> None:
        self._set_status(text)
        messagebox.showerror(PRODUCT, text, parent=self.root)

    def _close(self) -> None:
        self.alive = False
        self.station.stop()
        self.root.destroy()


def run(station: Station | None = None, web_url: str | None = None) -> None:
    root = tk.Tk()
    App(root, station=station, web_url=web_url)
    root.mainloop()


def _set_entry(widget: ttk.Entry, value: str) -> None:
    widget.delete(0, "end")
    widget.insert(0, value)


def _read_number(raw: str, minimum: float, maximum: float) -> float | None:
    try:
        value = float(str(raw).replace(",", "."))
    except ValueError:
        return None
    if value < minimum or value > maximum:
        return None
    return value


def _part_path(take: Take, part: str) -> Path | None:
    if part == "envio":
        return take.envio
    if part == "recepcion":
        return take.recepcion
    return take.primary


def _draw_lamp(canvas: tk.Canvas, mode: str) -> None:
    color = {"timed": TX, "threshold": RX}.get(mode, "#5c6b7a")
    canvas.delete("all")
    canvas.create_oval(2, 2, 14, 14, fill=color, outline="")


def _draw_bar(canvas: tk.Canvas, value: float, color: str) -> None:
    width = max(canvas.winfo_width(), 120)
    height = max(canvas.winfo_height(), 22)
    span = max(0.0, min(100.0, value)) / 100.0 * width
    canvas.delete("all")
    canvas.create_rectangle(0, 0, width, height, fill="#0c1218", outline="")
    canvas.create_rectangle(0, 3, span, height - 3, fill=color, outline="")


def _draw_spectrum(canvas: tk.Canvas, bands: list[float]) -> None:
    width = max(canvas.winfo_width(), 240)
    height = max(canvas.winfo_height(), 80)
    canvas.delete("all")
    canvas.create_rectangle(0, 0, width, height, fill="#0c1218", outline="")
    count = max(len(bands), 1)
    gap = 4
    bar_width = max(2, (width - gap * (count + 1)) / count)
    for index, band in enumerate(bands):
        amount = max(0.0, min(100.0, band)) / 100.0
        bar_height = amount * (height - 16)
        x = gap + index * (bar_width + gap)
        color = TX if index < count / 2 else RX
        canvas.create_rectangle(x, height - 8 - bar_height, x + bar_width, height - 8, fill=color, outline="")


def _open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - abre la carpeta de mensajes del operador
        return
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.run(command, check=False)
