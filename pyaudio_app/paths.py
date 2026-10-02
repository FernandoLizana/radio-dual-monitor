"""Rutas del proyecto, independientes de la máquina donde se ejecute."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RECORDINGS_DIR = ROOT / "recordings"
DB_PATH = DATA_DIR / "usuarios.db"
WEB_HOST = "127.0.0.1"
WEB_PORT = 8765
