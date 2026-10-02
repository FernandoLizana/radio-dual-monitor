"""Estado compartido por la consola de escritorio y la consola web."""

from __future__ import annotations

import threading
from pathlib import Path

from pyaudio_app.auth import UserStore
from pyaudio_app.engine import AudioEngine
from pyaudio_app.paths import DB_PATH, RECORDINGS_DIR
from pyaudio_app.storage import SavedClip
from pyaudio_app.wavutil import BAND_COUNT, Levels


class Station:
    def __init__(self, recordings_dir: Path = RECORDINGS_DIR, db_path: Path = DB_PATH) -> None:
        self.engine = AudioEngine(recordings_dir)
        self.users = UserStore(db_path)
        self.recordings_dir = recordings_dir
        self._lock = threading.Lock()
        self.mode = "idle"
        self.status = "Listo para escuchar el transmisor."
        self.envio = 0.0
        self.recepcion = 0.0
        self.channels = 0
        self.bands = tuple(0.0 for _ in range(BAND_COUNT))
        self.error = ""
        self.revision = 0

    def list_inputs(self) -> list[tuple[int, str]]:
        return self.engine.list_inputs()

    def record(self, device_index: int | None, seconds: float) -> str | None:
        if self.engine.busy:
            return "Ya hay una captura en curso."
        with self._lock:
            self.mode = "timed"
            self.error = ""
            self.status = "Grabando el espectro..."
        self.engine.record_timed(
            device_index,
            seconds,
            on_level=self._on_level,
            on_status=self._on_status,
            on_saved=self._on_saved,
            on_error=self._on_error,
            on_finished=self._on_finished,
        )
        return None

    def listen(self, device_index: int | None, threshold: float, silence_seconds: float) -> str | None:
        if self.engine.busy:
            return "Ya hay una captura en curso."
        with self._lock:
            self.mode = "threshold"
            self.error = ""
            self.status = "Escuchando el transmisor..."
        self.engine.listen_threshold(
            device_index,
            threshold,
            silence_seconds,
            on_level=self._on_level,
            on_status=self._on_status,
            on_saved=self._on_saved,
            on_error=self._on_error,
            on_finished=self._on_finished,
        )
        return None

    def stop(self) -> None:
        self.engine.stop()

    def play(self, path: Path) -> str | None:
        if self.engine.busy:
            return "Detén la captura antes de reproducir por los altavoces."
        self.engine.play(
            path,
            on_status=self._on_status,
            on_error=self._on_error,
            on_finished=lambda: None,
        )
        return None

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "mode": self.mode,
                "status": self.status,
                "envio": self.envio,
                "recepcion": self.recepcion,
                "channels": self.channels,
                "bands": list(self.bands),
                "error": self.error,
                "revision": self.revision,
                "busy": self.engine.busy,
            }

    def _on_level(self, levels: Levels) -> None:
        with self._lock:
            self.envio = levels.envio
            self.recepcion = levels.recepcion
            self.channels = levels.channels
            self.bands = levels.bands

    def _on_status(self, text: str) -> None:
        with self._lock:
            self.status = text

    def _on_saved(self, _clip: SavedClip) -> None:
        with self._lock:
            self.revision += 1

    def _on_error(self, text: str) -> None:
        with self._lock:
            self.error = text
            self.status = text

    def _on_finished(self) -> None:
        with self._lock:
            self.mode = "idle"
            self.envio = 0.0
            self.recepcion = 0.0
            self.channels = 0
            self.bands = tuple(0.0 for _ in range(BAND_COUNT))
