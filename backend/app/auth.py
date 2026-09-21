from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path


def _hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"{base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def _verify(password: str, encoded: str) -> bool:
    salt, expected = encoded.split("$", 1)
    actual = _hash(password, base64.urlsafe_b64decode(salt.encode())).split("$", 1)[1]
    return hmac.compare_digest(actual, expected)


class AuthStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at REAL NOT NULL)")

    def register(self, email: str, password: str) -> dict:
        user_id = secrets.token_urlsafe(12)
        try:
            with sqlite3.connect(self.path) as db:
                db.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user_id, email.lower().strip(), _hash(password), time.time()))
        except sqlite3.IntegrityError as exc:
            raise ValueError("An account with that email already exists") from exc
        return {"id": user_id, "email": email.lower().strip()}

    def login(self, email: str, password: str) -> tuple[dict, str]:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
        if not row or not _verify(password, row[2]):
            raise ValueError("Invalid email or password")
        token = secrets.token_urlsafe(32)
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (hashlib.sha256(token.encode()).hexdigest(), row[0], time.time() + 60 * 60 * 24 * 7))
        return {"id": row[0], "email": row[1]}, token

    def user_for_token(self, token: str | None) -> dict | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT users.id, users.email FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token_hash = ? AND sessions.expires_at > ?", (digest, time.time())).fetchone()
        return {"id": row[0], "email": row[1]} if row else None

    def logout(self, token: str | None) -> None:
        if token:
            with sqlite3.connect(self.path) as db:
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
