"""Guarda cada mensaje en carpetas de mes: espectro, envío y recepción."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pyaudio_app.wavutil import split_stereo, wav_duration, write_wav


@dataclass(frozen=True)
class SavedClip:
    primary_path: Path
    left_path: Path | None
    right_path: Path | None
    channels: int
    seconds: float


@dataclass(frozen=True)
class Take:
    """Un mensaje del transmisor, con sus canales si el micrófono es estéreo."""

    name: str
    modified: datetime
    seconds: float
    espectro: Path | None
    envio: Path | None
    recepcion: Path | None
    mono: Path | None

    @property
    def kind(self) -> str:
        if self.espectro:
            return "Espectro"
        if self.mono:
            return "Mono"
        return "Canal"

    @property
    def primary(self) -> Path | None:
        return self.espectro or self.mono or self.envio or self.recepcion


def save_clip(recordings_dir: Path, frames: bytes, channels: int, rate: int) -> SavedClip:
    if not frames or channels < 1 or rate < 1:
        raise ValueError("No hay audio para guardar.")
    paths = _output_paths(recordings_dir, channels)
    seconds = len(frames) / (channels * 2 * rate)
    if channels >= 2:
        write_wav(paths["stereo"], frames, 2, rate)
        split_stereo(paths["stereo"], paths["left"], paths["right"])
        return SavedClip(paths["stereo"], paths["left"], paths["right"], 2, seconds)
    write_wav(paths["mono"], frames, 1, rate)
    return SavedClip(paths["mono"], None, None, 1, seconds)


_FOLDERS = {
    "Espectro": "espectro",
    "Estereo": "espectro",
    "Envio": "envio",
    "Canal_1": "envio",
    "Recepcion": "recepcion",
    "Canal_2": "recepcion",
    "Mono": "mono",
}
_PREFERRED = {"Espectro", "Envio", "Recepcion", "Mono"}


def list_takes(recordings_dir: Path) -> list[Take]:
    if not recordings_dir.exists():
        return []
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for folder, field in _FOLDERS.items():
        for path in recordings_dir.glob(f"*/{folder}/*.wav"):
            try:
                seconds = wav_duration(path)
            except (wave.Error, EOFError, OSError):
                continue
            key = (path.parent.parent.name, path.stem)
            slot = grouped.setdefault(
                key,
                {
                    "seconds": 0.0,
                    "modified": None,
                    "espectro": None,
                    "envio": None,
                    "recepcion": None,
                    "mono": None,
                },
            )
            if slot[field] is None or folder in _PREFERRED:
                slot[field] = path
            modified = datetime.fromtimestamp(path.stat().st_mtime)
            current = slot["modified"]
            if not isinstance(current, datetime) or modified > current:
                slot["modified"] = modified
            if field in {"espectro", "mono"} or float(slot["seconds"]) == 0.0:
                slot["seconds"] = seconds
    takes: list[Take] = []
    for (_month, stem), slot in grouped.items():
        modified = slot["modified"]
        if not isinstance(modified, datetime):
            continue
        takes.append(
            Take(
                name=f"{stem}.wav",
                modified=modified,
                seconds=float(slot["seconds"]),
                espectro=_as_path(slot["espectro"]),
                envio=_as_path(slot["envio"]),
                recepcion=_as_path(slot["recepcion"]),
                mono=_as_path(slot["mono"]),
            )
        )
    takes.sort(key=lambda item: item.modified, reverse=True)
    return takes


def _output_paths(recordings_dir: Path, channels: int) -> dict[str, Path]:
    now = datetime.now()
    month_dir = recordings_dir / now.strftime("%Y-%m")
    stamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    if channels >= 2:
        folders = {
            "stereo": month_dir / "Espectro",
            "left": month_dir / "Envio",
            "right": month_dir / "Recepcion",
        }
        key = "stereo"
    else:
        folders = {"mono": month_dir / "Mono"}
        key = "mono"
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    name = f"{stamp}.wav"
    suffix = 2
    while (folders[key] / name).exists():
        name = f"{stamp}_{suffix}.wav"
        suffix += 1
    return {label: folder / name for label, folder in folders.items()}


def _as_path(value: object) -> Path | None:
    return value if isinstance(value, Path) else None
