"""Prepara Espectro en este equipo: entorno virtual y dependencias.

Uso, desde la carpeta del proyecto:

    python install.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "requirements.txt"
MIN_VERSION = (3, 11)


def main() -> None:
    if sys.version_info < MIN_VERSION:
        major, minor = MIN_VERSION
        sys.exit(f"Se necesita Python {major}.{minor} o superior. Este es {sys.version.split()[0]}.")
    if not REQUIREMENTS.is_file():
        sys.exit("No está requirements.txt junto a install.py.")

    venv_python = _venv_python()
    if not venv_python.is_file():
        print("Creando el entorno virtual .venv ...")
        subprocess.check_call([sys.executable, "-m", "venv", str(ROOT / ".venv")])

    print("Instalando dependencias ...")
    try:
        subprocess.check_call([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([str(venv_python), "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    except subprocess.CalledProcessError:
        _print_audio_hint()
        sys.exit(1)

    runner = venv_python
    print()
    print("Espectro quedó instalado en este equipo.")
    print("Para abrirlo:")
    print(f"  {runner} main.py")


def _venv_python() -> Path:
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def _print_audio_hint() -> None:
    print()
    print("La instalación se detuvo. PyAudio necesita la biblioteca PortAudio.")
    if sys.platform.startswith("linux"):
        print("En Debian o Ubuntu:")
        print("  sudo apt install portaudio19-dev python3-dev")
        print("En Fedora:")
        print("  sudo dnf install portaudio-devel python3-devel")
    elif sys.platform == "darwin":
        print("En macOS, con Homebrew:")
        print("  brew install portaudio")
    else:
        print("En Windows, usa Python 3.11 o 3.12. Esas versiones traen rueda de PyAudio y no hace falta compilar.")
    print("Después vuelve a ejecutar: python install.py")


if __name__ == "__main__":
    main()
