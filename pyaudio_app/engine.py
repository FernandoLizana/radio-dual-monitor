"""Grabación, escucha por umbral y reproducción en segundo plano."""

from __future__ import annotations

import threading
import time
import wave
from pathlib import Path
from typing import Callable

import pyaudio

from pyaudio_app.storage import SavedClip, save_clip
from pyaudio_app.wavutil import Levels, analyze

CHUNK = 1024
SAMPLE_WIDTH = 2
_RATES = (44100, 48000, 16000)
LevelCallback = Callable[[Levels], None]
StatusCallback = Callable[[str], None]
SavedCallback = Callable[[SavedClip], None]
ErrorCallback = Callable[[str], None]
FinishedCallback = Callable[[], None]


def _listening_again(channels: int) -> str:
    if channels < 2:
        return "Guardado en un solo canal. Escuchando el transmisor..."
    return "Espectro guardado. Escuchando el transmisor..."


class AudioEngine:
    def __init__(self, recordings_dir: Path) -> None:
        self.recordings_dir = recordings_dir
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._playback_stop = threading.Event()
        self._playback_thread: threading.Thread | None = None

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def list_inputs(self) -> list[tuple[int, str]]:
        audio = pyaudio.PyAudio()
        try:
            devices: list[tuple[int, str]] = []
            for index in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(index)
                if int(info.get("maxInputChannels", 0)) < 1:
                    continue
                name = str(info.get("name", f"Dispositivo {index}"))
                host_index = int(info.get("hostApi", 0))
                host = str(audio.get_host_api_info_by_index(host_index).get("name", "")).strip()
                label = f"{name} · {host}" if host else name
                devices.append((index, label))
            visible = [item for item in devices if "WDM-KS" not in item[1]]
            return visible or devices
        finally:
            audio.terminate()

    def stop(self) -> None:
        self._stop.set()
        self._playback_stop.set()
        thread = self._thread
        if thread and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=3)
        playback = self._playback_thread
        if playback and playback.is_alive() and threading.current_thread() is not playback:
            playback.join(timeout=2)

    def record_timed(
        self,
        device_index: int | None,
        seconds: float,
        on_level: LevelCallback,
        on_status: StatusCallback,
        on_saved: SavedCallback,
        on_error: ErrorCallback,
        on_finished: FinishedCallback,
    ) -> None:
        self._start(
            lambda: self._record_timed(device_index, seconds, on_level, on_status, on_saved),
            on_error,
            on_finished,
        )

    def listen_threshold(
        self,
        device_index: int | None,
        threshold: float,
        silence_seconds: float,
        on_level: LevelCallback,
        on_status: StatusCallback,
        on_saved: SavedCallback,
        on_error: ErrorCallback,
        on_finished: FinishedCallback,
    ) -> None:
        self._start(
            lambda: self._listen_threshold(
                device_index, threshold, silence_seconds, on_level, on_status, on_saved
            ),
            on_error,
            on_finished,
        )

    def play(
        self,
        path: Path,
        on_status: StatusCallback,
        on_error: ErrorCallback,
        on_finished: FinishedCallback,
    ) -> None:
        if self.busy:
            on_error("Detén la grabación antes de reproducir.")
            return
        self._playback_stop.set()
        playback = self._playback_thread
        if playback and playback.is_alive():
            playback.join(timeout=2)
        self._playback_stop.clear()

        def runner() -> None:
            try:
                self._play(path, on_status)
            except Exception as exc:
                on_error(str(exc))
            finally:
                on_finished()

        self._playback_thread = threading.Thread(target=runner, daemon=True)
        self._playback_thread.start()

    def _start(self, work: Callable[[], None], on_error: ErrorCallback, on_finished: FinishedCallback) -> None:
        if self.busy:
            on_error("Ya hay una grabación en curso.")
            return
        self._playback_stop.set()
        self._stop.clear()

        def runner() -> None:
            try:
                work()
            except Exception as exc:
                on_error(str(exc))
            finally:
                on_finished()

        self._thread = threading.Thread(target=runner, daemon=True)
        self._thread.start()

    def _record_timed(
        self,
        device_index: int | None,
        seconds: float,
        on_level: LevelCallback,
        on_status: StatusCallback,
        on_saved: SavedCallback,
    ) -> None:
        on_status("Grabando el espectro...")
        audio, stream, channels, rate = self._open_input(device_index)
        frames: list[bytes] = []
        try:
            deadline = time.time() + seconds
            while time.time() < deadline and not self._stop.is_set():
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
                on_level(analyze(data, channels))
            self._store(frames, channels, rate, on_saved, on_status, discarded_label="Toma cancelada")
        finally:
            self._close(audio, stream)

    def _listen_threshold(
        self,
        device_index: int | None,
        threshold: float,
        silence_seconds: float,
        on_level: LevelCallback,
        on_status: StatusCallback,
        on_saved: SavedCallback,
    ) -> None:
        on_status("Escuchando el transmisor...")
        audio, stream, channels, rate = self._open_input(device_index)
        captured: list[bytes] = []
        captured_bytes = 0
        recording = False
        silence_deadline = 0.0
        max_bytes = int(channels * SAMPLE_WIDTH * rate * 600)
        try:
            while not self._stop.is_set():
                data = stream.read(CHUNK, exception_on_overflow=False)
                levels = analyze(data, channels)
                on_level(levels)
                heard = max(levels.envio, levels.recepcion)
                if heard >= threshold:
                    if not recording:
                        captured = []
                        captured_bytes = 0
                        recording = True
                        on_status("Transmisor detectado: guardando envío y recepción...")
                    captured.append(data)
                    captured_bytes += len(data)
                    silence_deadline = time.time() + silence_seconds
                    if captured_bytes >= max_bytes:
                        self._store(captured, channels, rate, on_saved, on_status, force=True)
                        captured = []
                        captured_bytes = 0
                        recording = False
                        on_status(_listening_again(channels))
                elif recording:
                    captured.append(data)
                    captured_bytes += len(data)
                    if time.time() >= silence_deadline:
                        self._store(captured, channels, rate, on_saved, on_status, force=True)
                        captured = []
                        captured_bytes = 0
                        recording = False
                        on_status(_listening_again(channels))
            if captured:
                self._store(captured, channels, rate, on_saved, on_status, force=True)
            else:
                on_status("Escucha detenida")
        finally:
            self._close(audio, stream)

    def _store(
        self,
        frames: list[bytes],
        channels: int,
        rate: int,
        on_saved: SavedCallback,
        on_status: StatusCallback,
        discarded_label: str = "Sin audio del transmisor",
        force: bool = False,
    ) -> None:
        payload = b"".join(frames)
        seconds = len(payload) / (channels * SAMPLE_WIDTH * rate) if rate else 0
        if not payload or (not force and seconds < 0.25):
            on_status(discarded_label)
            return
        clip = save_clip(self.recordings_dir, payload, channels, rate)
        on_saved(clip)
        if channels < 2:
            on_status("Guardado en un solo canal. El espectro completo necesita envío y recepción.")
        else:
            on_status(f"Espectro guardado: {clip.primary_path.name}")

    def _play(self, path: Path, on_status: StatusCallback) -> None:
        audio = pyaudio.PyAudio()
        stream = None
        try:
            with wave.open(str(path), "rb") as handle:
                stream = audio.open(
                    format=audio.get_format_from_width(handle.getsampwidth()),
                    channels=handle.getnchannels(),
                    rate=handle.getframerate(),
                    output=True,
                )
                on_status(f"Reproduciendo {path.name}")
                data = handle.readframes(CHUNK)
                while data and not self._playback_stop.is_set():
                    stream.write(data)
                    data = handle.readframes(CHUNK)
            if self._playback_stop.is_set():
                on_status("Reproducción detenida")
            else:
                on_status("Reproducción terminada")
        finally:
            self._close(audio, stream)

    def _open_input(self, device_index: int | None) -> tuple[pyaudio.PyAudio, pyaudio.Stream, int, int]:
        audio = pyaudio.PyAudio()
        try:
            if device_index is None:
                info = audio.get_default_input_device_info()
                device_index = int(info["index"])
            else:
                info = audio.get_device_info_by_index(device_index)
            max_channels = int(info.get("maxInputChannels", 0))
            if max_channels < 1:
                raise RuntimeError("El dispositivo elegido no tiene entrada de audio.")
            channel_options = (2, 1) if max_channels >= 2 else (1,)
            last_error: Exception | None = None
            for channels in channel_options:
                for rate in _RATES:
                    try:
                        stream = audio.open(
                            format=pyaudio.paInt16,
                            channels=channels,
                            rate=rate,
                            input=True,
                            input_device_index=device_index,
                            frames_per_buffer=CHUNK,
                        )
                        return audio, stream, channels, rate
                    except OSError as exc:
                        last_error = exc
            raise RuntimeError(f"No se pudo abrir el micrófono. {last_error}")
        except Exception:
            audio.terminate()
            raise

    @staticmethod
    def _close(audio: pyaudio.PyAudio | None, stream: pyaudio.Stream | None) -> None:
        if stream is not None:
            try:
                if stream.is_active():
                    stream.stop_stream()
            except OSError:
                pass
            try:
                stream.close()
            except OSError:
                pass
        if audio is not None:
            audio.terminate()
