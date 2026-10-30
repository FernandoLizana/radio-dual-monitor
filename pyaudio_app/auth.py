"""Usuarios locales con contraseña hasheada."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from pathlib import Path

DEFAULT_USER = "Admin"
PASSWORD_ENV = "RADIO_ADMIN_PASSWORD"
INITIAL_PASSWORD_FILE = "clave_inicial.txt"
_ITERATIONS = 200_000


def first_run_hint() -> str:
    return (
        f"Primera vez en este equipo: usuario {DEFAULT_USER}. La contraseña es la de "
        f"{PASSWORD_ENV} o la que quedó en data/{INITIAL_PASSWORD_FILE}."
    )


class UserStore:
    def __init__(self, db_path: Path, initial_password: str | None = None) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initial_password = initial_password
        self._init_db()

    def authenticate(self, username: str, password: str) -> bool:
        username = username.strip()
        if not username or not password:
            return False
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT salt, password_hash FROM usuarios WHERE usuario = ?",
                (username,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return False
        salt = bytes.fromhex(row["salt"])
        expected = bytes.fromhex(row["password_hash"])
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
        return hmac.compare_digest(candidate, expected)

    def _init_db(self) -> None:
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS usuarios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        usuario TEXT NOT NULL UNIQUE,
                        salt TEXT NOT NULL,
                        password_hash TEXT NOT NULL
                    )
                    """
                )
                count = connection.execute("SELECT COUNT(*) AS total FROM usuarios").fetchone()["total"]
                if count == 0:
                    self._insert(connection, DEFAULT_USER, self._first_password())
        finally:
            connection.close()

    def _first_password(self) -> str:
        # Sin contraseña conocida en el código: se toma del entorno o se genera
        # una al azar y se deja solo en este equipo, junto a la base.
        password = self._initial_password or os.environ.get(PASSWORD_ENV, "")
        if password:
            return password
        password = secrets.token_urlsafe(9)
        path = self.db_path.parent / INITIAL_PASSWORD_FILE
        path.write_text(f"{DEFAULT_USER} / {password}\n", encoding="utf-8")
        print(f"Cuenta inicial creada: {DEFAULT_USER} / {password} (guardada en {path})")
        return password

    def _insert(self, connection: sqlite3.Connection, username: str, password: str) -> None:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
        connection.execute(
            "INSERT INTO usuarios (usuario, salt, password_hash) VALUES (?, ?, ?)",
            (username, salt.hex(), digest.hex()),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
