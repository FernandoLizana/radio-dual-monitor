import array
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pyaudio_app.auth import DEFAULT_USER, INITIAL_PASSWORD_FILE, PASSWORD_ENV, UserStore
from pyaudio_app.storage import list_takes, save_clip
from pyaudio_app.wavutil import channel_levels, rms_level, spectrum_bands, split_stereo, wav_duration, write_wav


class RmsTests(unittest.TestCase):
    def test_silence_is_zero(self) -> None:
        self.assertEqual(rms_level(b"\x00\x00" * 200), 0.0)

    def test_full_scale_sine_is_near_707(self) -> None:
        samples = array.array(
            "h",
            (int(32767 * math.sin(2 * math.pi * i / 32)) for i in range(4096)),
        )
        level = rms_level(samples.tobytes())
        self.assertAlmostEqual(level, 707.1, delta=5)


class ChannelTests(unittest.TestCase):
    def test_envio_and_recepcion_are_independent(self) -> None:
        stereo = array.array("h")
        for _ in range(128):
            stereo.append(1000)
            stereo.append(-2000)
        envio, recepcion = channel_levels(stereo.tobytes(), 2)
        self.assertAlmostEqual(envio, 1000 / 32768 * 1000, delta=0.2)
        self.assertAlmostEqual(recepcion, 2000 / 32768 * 1000, delta=0.2)

    def test_silence_has_no_spectrum_and_a_tone_does(self) -> None:
        silence = spectrum_bands(b"\x00\x00" * 2048, 1)
        tone = array.array("h", (int(32767 * math.sin(2 * math.pi * i / 32)) for i in range(2048)))
        bands = spectrum_bands(tone.tobytes(), 1)
        self.assertEqual(len(silence), 24)
        self.assertLess(max(silence), 5)
        self.assertGreater(max(bands), 30)


class SplitTests(unittest.TestCase):
    def test_split_keeps_each_channel(self) -> None:
        left = array.array("h", [1000] * 64)
        right = array.array("h", [-2000] * 64)
        stereo = array.array("h")
        for sample_left, sample_right in zip(left, right):
            stereo.append(sample_left)
            stereo.append(sample_right)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "mix.wav"
            left_path = root / "left.wav"
            right_path = root / "right.wav"
            write_wav(source, stereo.tobytes(), 2, 44100)
            split_stereo(source, left_path, right_path)
            self.assertAlmostEqual(wav_duration(left_path), 64 / 44100, places=5)
            self.assertEqual(_read_samples(left_path), list(left))
            self.assertEqual(_read_samples(right_path), list(right))


class StorageTests(unittest.TestCase):
    def test_save_stereo_creates_month_folders(self) -> None:
        frames = (array.array("h", [1, -1] * 200)).tobytes()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            clip = save_clip(root, frames, 2, 8000)
            self.assertTrue(clip.primary_path.exists())
            self.assertTrue(clip.left_path is not None and clip.left_path.exists())
            self.assertTrue(clip.right_path is not None and clip.right_path.exists())
            self.assertEqual(clip.primary_path.parent.name, "Espectro")
            self.assertEqual(clip.left_path.parent.name, "Envio")
            self.assertEqual(clip.right_path.parent.name, "Recepcion")
            takes = list_takes(root)
            self.assertEqual(len(takes), 1)
            self.assertEqual(takes[0].kind, "Espectro")
            self.assertIsNotNone(takes[0].envio)
            self.assertIsNotNone(takes[0].recepcion)


class AuthTests(unittest.TestCase):
    def test_default_user_and_rejects_wrong_password(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = UserStore(Path(folder) / "usuarios.db", initial_password="clave-local")
            self.assertTrue(store.authenticate(DEFAULT_USER, "clave-local"))
            self.assertFalse(store.authenticate(DEFAULT_USER, "otra"))
            self.assertFalse(store.authenticate("nadie", "clave-local"))

    def test_password_comes_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {PASSWORD_ENV: "desde-env"}):
            store = UserStore(Path(folder) / "usuarios.db")
            self.assertTrue(store.authenticate(DEFAULT_USER, "desde-env"))
            self.assertFalse((Path(folder) / INITIAL_PASSWORD_FILE).exists())

    def test_without_env_generates_random_password(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != PASSWORD_ENV}
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, env, clear=True):
            store = UserStore(Path(folder) / "usuarios.db")
            saved = (Path(folder) / INITIAL_PASSWORD_FILE).read_text(encoding="utf-8")
            user, password = saved.strip().split(" / ")
            self.assertEqual(user, DEFAULT_USER)
            self.assertTrue(store.authenticate(DEFAULT_USER, password))
            self.assertFalse(store.authenticate(DEFAULT_USER, "Admin1234"))


def _read_samples(path: Path) -> list[int]:
    import wave

    with wave.open(str(path), "rb") as handle:
        raw = handle.readframes(handle.getnframes())
    samples = array.array("h")
    samples.frombytes(raw)
    return list(samples)


if __name__ == "__main__":
    unittest.main()
