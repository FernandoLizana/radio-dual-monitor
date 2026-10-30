"""Consola web local de Espectro. Solo escucha en este computador."""

from __future__ import annotations

import re
import threading
from functools import wraps
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, session, url_for

from pyaudio_app.auth import first_run_hint
from pyaudio_app.brand import COMPANY, PRODUCT, STEPS, TAGLINE
from pyaudio_app.paths import DATA_DIR, WEB_HOST, WEB_PORT
from pyaudio_app.station import Station
from pyaudio_app.storage import Take, list_takes

_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_NAME = re.compile(r"^[A-Za-z0-9._-]+\.wav$")
_KINDS = {"Espectro", "Envio", "Recepcion", "Mono", "Estereo", "Canal_1", "Canal_2"}


def create_app(station: Station, secret_key: str | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent / "static"),
    )
    app.secret_key = secret_key or _load_secret()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user"):
                if request.path.startswith("/api/"):
                    return jsonify(error="No autorizado"), 401
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped

    @app.get("/login")
    def login():
        if session.get("user"):
            return redirect(url_for("console"))
        return render_template(
            "login.html",
            company=COMPANY,
            product=PRODUCT,
            tagline=TAGLINE,
            steps=STEPS,
            first_run=first_run_hint(),
            error="",
        )

    @app.post("/login")
    def login_submit():
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if station.users.authenticate(username, password):
            session["user"] = username.strip()
            return redirect(url_for("console"))
        return render_template(
            "login.html",
            company=COMPANY,
            product=PRODUCT,
            tagline=TAGLINE,
            steps=STEPS,
            first_run=first_run_hint(),
            error="Acceso denegado. Revisa los datos.",
        ), 401

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def console():
        return render_template(
            "console.html",
            company=COMPANY,
            product=PRODUCT,
            tagline=TAGLINE,
            steps=STEPS,
            user=session.get("user", ""),
        )

    @app.get("/api/status")
    @login_required
    def api_status():
        return jsonify(station.snapshot())

    @app.get("/api/devices")
    @login_required
    def api_devices():
        try:
            devices = [{"index": index, "name": name} for index, name in station.list_inputs()]
        except Exception as exc:
            return jsonify(error=str(exc)), 500
        return jsonify(devices=devices)

    @app.get("/api/recordings")
    @login_required
    def api_recordings():
        return jsonify(recordings=[_take_payload(take) for take in list_takes(station.recordings_dir)])

    @app.post("/api/record")
    @login_required
    def api_record():
        body = request.get_json(silent=True) or {}
        seconds = _number(body.get("seconds"), 1, 300)
        if seconds is None:
            return jsonify(error="La duración debe estar entre 1 y 300 segundos."), 400
        error = station.record(_device_index(body.get("device_index")), seconds)
        if error:
            return jsonify(error=error), 409
        return jsonify(ok=True)

    @app.post("/api/listen")
    @login_required
    def api_listen():
        body = request.get_json(silent=True) or {}
        threshold = _number(body.get("threshold"), 1, 1000)
        silence = _number(body.get("silence"), 1, 30)
        if threshold is None or silence is None:
            return jsonify(error="Revisa el umbral (1-1000) y el silencio (1-30 s)."), 400
        error = station.listen(_device_index(body.get("device_index")), threshold, silence)
        if error:
            return jsonify(error=error), 409
        return jsonify(ok=True)

    @app.post("/api/stop")
    @login_required
    def api_stop():
        station.stop()
        return jsonify(ok=True)

    @app.get("/audio/<month>/<kind>/<filename>")
    @login_required
    def audio(month: str, kind: str, filename: str):
        path = _safe_audio(station.recordings_dir, month, kind, filename)
        return send_file(path, mimetype="audio/wav", conditional=True)

    return app


def start_in_background(station: Station, host: str = WEB_HOST, port: int = WEB_PORT) -> str | None:
    import socket

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError:
        return None
    finally:
        probe.close()

    app = create_app(station)
    thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, threaded=True, use_reloader=False),
        name="espectro-web",
        daemon=True,
    )
    thread.start()
    return f"http://{host}:{port}"


def main() -> None:
    from pyaudio_app.station import Station as StationRuntime

    station = StationRuntime()
    app = create_app(station)
    print(f"Consola web de {PRODUCT}: http://{WEB_HOST}:{WEB_PORT}")
    app.run(host=WEB_HOST, port=WEB_PORT, threaded=True, use_reloader=False)


def _load_secret() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "web_secret"
    if path.exists():
        stored = path.read_text(encoding="utf-8").strip()
        if stored:
            return stored
    import secrets

    stored = secrets.token_hex(32)
    path.write_text(stored, encoding="utf-8")
    return stored


def _number(value: object, low: float, high: float) -> float | None:
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if number < low or number > high:
        return None
    return number


def _device_index(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _take_payload(take: Take) -> dict[str, object]:
    return {
        "name": take.name,
        "modified": take.modified.strftime("%Y-%m-%d %H:%M:%S"),
        "seconds": round(take.seconds, 1),
        "kind": take.kind,
        "espectro": _audio_url(take.espectro),
        "envio": _audio_url(take.envio),
        "recepcion": _audio_url(take.recepcion),
        "mono": _audio_url(take.mono),
    }


def _audio_url(path: Path | None) -> str | None:
    if path is None:
        return None
    return f"/audio/{path.parent.parent.name}/{path.parent.name}/{path.name}"


def _safe_audio(root: Path, month: str, kind: str, filename: str) -> Path:
    if not _MONTH.match(month) or kind not in _KINDS or not _NAME.match(filename):
        abort(404)
    base = root.resolve()
    path = (base / month / kind / filename).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        abort(404)
    return path


if __name__ == "__main__":
    main()
