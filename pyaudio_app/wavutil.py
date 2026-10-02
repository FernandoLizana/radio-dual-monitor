"""Operaciones sobre PCM de 16 bits, sin abrir el micrófono."""

from __future__ import annotations

import array
import math
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

BAND_COUNT = 24


@dataclass(frozen=True)
class Levels:
    envio: float
    recepcion: float
    bands: tuple[float, ...]
    channels: int


def rms_level(frame: bytes) -> float:
    """Nivel RMS en la misma escala que la beta (0 en silencio, ~707 en seno a fondo)."""
    return _rms_samples(_samples_from_frames(frame))


def channel_levels(frame: bytes, channels: int) -> tuple[float, float]:
    """Niveles de envío (izquierda) y recepción (derecha)."""
    samples = _samples_from_frames(frame)
    if not samples:
        return 0.0, 0.0
    if channels >= 2:
        if len(samples) % 2:
            samples = samples[:-1]
        return _rms_samples(samples[0::2]), _rms_samples(samples[1::2])
    return _rms_samples(samples), 0.0


def spectrum_bands(frame: bytes, channels: int, bands: int = BAND_COUNT) -> list[float]:
    """Energía del mensaje completo, partida en bandas de 0 a 100."""
    samples = _samples_from_frames(frame)
    if channels >= 2 and len(samples) >= 2:
        if len(samples) % 2:
            samples = samples[:-1]
        mixed = np.fromiter(
            ((samples[index] + samples[index + 1]) * 0.5 for index in range(0, len(samples), 2)),
            dtype=np.float32,
            count=len(samples) // 2,
        )
    else:
        mixed = np.asarray(samples, dtype=np.float32)
    if mixed.size < 32:
        return [0.0] * bands
    window = np.hanning(mixed.size).astype(np.float32)
    magnitudes = np.abs(np.fft.rfft(mixed * window))[1:]
    if magnitudes.size == 0:
        return [0.0] * bands
    chunks = np.array_split(magnitudes, bands)
    shown: list[float] = []
    for chunk in chunks:
        if chunk.size == 0:
            shown.append(0.0)
            continue
        power = float(np.mean(chunk)) / 32768.0
        decibels = 20.0 * math.log10(power + 1e-9)
        scaled = (decibels + 80.0) / 80.0 * 100.0
        shown.append(max(0.0, min(100.0, scaled)))
    return shown


def analyze(frame: bytes, channels: int) -> Levels:
    envio, recepcion = channel_levels(frame, channels)
    return Levels(envio, recepcion, tuple(spectrum_bands(frame, channels)), channels)


def write_wav(path: Path, frames: bytes, channels: int, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames)


def split_stereo(source: Path, left_path: Path, right_path: Path) -> None:
    """Separa un WAV estéreo de 16 bits en dos archivos mono."""
    with wave.open(str(source), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if channels != 2 or width != 2:
        raise ValueError("Solo se pueden separar WAV estéreo de 16 bits.")

    samples = _samples_from_frames(frames)
    if len(samples) % 2:
        samples = samples[:-1]
    left = array.array("h", samples[0::2])
    right = array.array("h", samples[1::2])
    write_wav(left_path, _frames_from_samples(left), 1, rate)
    write_wav(right_path, _frames_from_samples(right), 1, rate)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate() or 1
        return handle.getnframes() / rate


def _rms_samples(samples: array.array) -> float:
    count = len(samples)
    if count == 0:
        return 0.0
    total = 0.0
    for sample in samples:
        normalized = sample / 32768.0
        total += normalized * normalized
    return math.sqrt(total / count) * 1000.0


def _samples_from_frames(frames: bytes) -> array.array:
    usable = frames[: len(frames) - (len(frames) % 2)]
    samples = array.array("h")
    if usable:
        samples.frombytes(usable)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _frames_from_samples(samples: array.array) -> bytes:
    outgoing = array.array("h", samples)
    if sys.byteorder != "little":
        outgoing.byteswap()
    return outgoing.tobytes()
