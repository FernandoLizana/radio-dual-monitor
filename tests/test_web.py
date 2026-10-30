import tempfile
import unittest
from pathlib import Path

from pyaudio_app.auth import DEFAULT_PASSWORD, DEFAULT_USER
from pyaudio_app.station import Station
from pyaudio_app.storage import save_clip
from pyaudio_app.web import create_app


class WebConsoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._folder = tempfile.TemporaryDirectory()
        root = Path(self._folder.name)
        frames = b"\x01\x00\xff\xff" * 80
        self.clip = save_clip(root / "recordings", frames, 2, 8000)
        station = Station(root / "recordings", root / "usuarios.db")
        self.client = create_app(station, secret_key="test-secret").test_client()

    def tearDown(self) -> None:
        self._folder.cleanup()

    def test_login_and_audio_stay_inside_recordings(self) -> None:
        anonymous = self.client.get("/")
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn("/login", anonymous.headers["Location"])

        denied = self.client.post("/login", data={"username": DEFAULT_USER, "password": "no"})
        self.assertEqual(denied.status_code, 401)
        self.assertIn("Acceso denegado".encode(), denied.data)

        entered = self.client.post(
            "/login",
            data={"username": DEFAULT_USER, "password": DEFAULT_PASSWORD},
            follow_redirects=True,
        )
        self.assertEqual(entered.status_code, 200)
        self.assertIn(b"Monitor de radio", entered.data)
        self.assertIn("Envío".encode(), entered.data)
        self.assertIn("Recepción".encode(), entered.data)

        status = self.client.get("/api/status")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["mode"], "idle")

        recordings = self.client.get("/api/recordings")
        payload = recordings.get_json()["recordings"]
        self.assertEqual(len(payload), 1)
        audio = self.client.get(payload[0]["espectro"])
        try:
            self.assertEqual(audio.status_code, 200)
            self.assertEqual(audio.mimetype, "audio/wav")
            self.assertTrue(audio.data.startswith(b"RIFF"))
        finally:
            audio.close()

        blocked = self.client.get("/audio/2026-09/Espectro/../secret.wav")
        self.assertEqual(blocked.status_code, 404)
        outside = self.client.get("/audio/2026-09/Espectro/not-a-take.txt")
        self.assertEqual(outside.status_code, 404)


if __name__ == "__main__":
    unittest.main()
