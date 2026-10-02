"""Arranca la estación de Espectro: consola de escritorio y consola web local."""

import tkinter as tk
from tkinter import messagebox

from pyaudio_app.brand import PRODUCT, WINDOW_TITLE
from pyaudio_app.paths import WEB_PORT


def main() -> None:
    missing = _missing_packages()
    if missing:
        root = tk.Tk()
        root.withdraw()
        joined = ", ".join(missing)
        messagebox.showerror(
            WINDOW_TITLE,
            f"Faltan paquetes: {joined}.\n\nInstálalos con:\npython -m pip install -r requirements.txt",
        )
        root.destroy()
        return

    from pyaudio_app.station import Station
    from pyaudio_app.ui import run
    from pyaudio_app.web import start_in_background

    station = Station()
    url = start_in_background(station)
    if url:
        print(f"Consola web de {PRODUCT}: {url}")
    else:
        print(f"La consola web no pudo iniciarse. El puerto {WEB_PORT} está en uso.")
    run(station, url)


def _missing_packages() -> list[str]:
    missing: list[str] = []
    for name in ("pyaudio", "flask", "numpy"):
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    return missing


if __name__ == "__main__":
    main()
