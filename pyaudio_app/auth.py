"""Usuarios locales con contraseña hasheada."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path

DEFAULT_USER = "Admin"
DEFAULT_PASSWORD = "Admin1234"
_ITERATIONS = 200_000


class UserStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
                    self._insert(connection, DEFAULT_USER, DEFAULT_PASSWORD)
        finally:
            connection.close()

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
