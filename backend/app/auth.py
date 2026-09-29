"""SQLite-backed authentication store with PBKDF2 password hashing and expiring bearer tokens."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path


TOKEN_EXPIRY = int(os.getenv("GRAPHMIND_TOKEN_EXPIRY_HOURS", "24")) * 3600


class AuthStore:
    def __init__(self, db_path: Path) -> None:
        self._db = str(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tokens (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
            """)

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000)
        return f"{salt}:{dk.hex()}"

    @staticmethod
    def _verify_password(password: str, stored: str) -> bool:
        try:
            salt, dk_hex = stored.split(":", 1)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000)
            return hmac.compare_digest(dk.hex(), dk_hex)
        except Exception:
            return False

    def register(self, email: str, password: str) -> dict:
        import uuid
        user_id = str(uuid.uuid4())
        pw_hash = self._hash_password(password)
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO users (id, email, password_hash, created_at) VALUES (?,?,?,?)",
                    (user_id, email, pw_hash, time.time()),
                )
            return {"id": user_id, "email": email}
        except sqlite3.IntegrityError:
            return {}

    def login(self, email: str, password: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not row or not self._verify_password(password, row["password_hash"]):
            return None
        token = secrets.token_urlsafe(32)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO tokens (token, user_id, created_at) VALUES (?,?,?)",
                (token, row["id"], time.time()),
            )
        return token

    def logout(self, token: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM tokens WHERE token=?", (token,))

    def user_for_token(self, token: str | None) -> dict | None:
        if not token:
            return None
        with self._conn() as conn:
            row = conn.execute(
                "SELECT t.created_at, u.id, u.email FROM tokens t "
                "JOIN users u ON u.id=t.user_id WHERE t.token=?",
                (token,),
            ).fetchone()
        if not row:
            return None
        if time.time() - row["created_at"] > TOKEN_EXPIRY:
            self.logout(token)
            return None
        return {"id": row["id"], "email": row["email"]}
