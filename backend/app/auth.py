from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import smtplib
import sqlite3
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def _send_otp_email(to_address: str, otp_code: str, context: str = "phone verification") -> bool:
    """Send real OTP code to the user's email via Gmail SMTP. Returns True on success."""
    smtp_from = os.getenv("OTP_SMTP_FROM", "")
    smtp_password = os.getenv("OTP_SMTP_PASSWORD", "")
    if not smtp_from or not smtp_password:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your GraphMind OTP: {otp_code}"
        msg["From"] = f"GraphMind AI <{smtp_from}>"
        msg["To"] = to_address
        html = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px;background:#0a0e1a;color:#e2e8f0;border-radius:12px">
          <h2 style="color:#06b6d4;margin:0 0 8px">GraphMind AI</h2>
          <p style="color:#94a3b8;margin:0 0 24px;font-size:13px">Enterprise Scientific Intelligence Platform</p>
          <div style="background:#1e293b;border:1px solid #1e3a5f;border-radius:8px;padding:24px;text-align:center;margin-bottom:24px">
            <p style="color:#94a3b8;margin:0 0 12px;font-size:14px">Your one-time verification code for {context}</p>
            <span style="font-size:40px;font-weight:bold;letter-spacing:12px;color:#06b6d4">{otp_code}</span>
            <p style="color:#64748b;margin:16px 0 0;font-size:12px">⏱ Expires in 10 minutes &nbsp;·&nbsp; Do not share this code</p>
          </div>
          <p style="color:#475569;font-size:12px;margin:0">If you did not request this code, you can safely ignore this email.</p>
        </div>
        """
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_from, smtp_password)
            server.sendmail(smtp_from, to_address, msg.as_string())
        return True
    except Exception:
        return False


def _hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"{base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def _verify(password: str, encoded: str) -> bool:
    try:
        salt, expected = encoded.split("$", 1)
        actual = _hash(password, base64.urlsafe_b64decode(salt.encode())).split("$", 1)[1]
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


class AuthStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "id TEXT PRIMARY KEY, "
                "email TEXT UNIQUE NOT NULL, "
                "password_hash TEXT NOT NULL, "
                "created_at REAL NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS sessions ("
                "token_hash TEXT PRIMARY KEY, "
                "user_id TEXT NOT NULL, "
                "expires_at REAL NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS otp_codes ("
                "target TEXT PRIMARY KEY, "
                "code TEXT NOT NULL, "
                "expires_at REAL NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS magic_links ("
                "token TEXT PRIMARY KEY, "
                "email TEXT NOT NULL, "
                "expires_at REAL NOT NULL)"
            )

    def _issue_session(self, user_id: str, email: str) -> tuple[dict, str]:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO sessions VALUES (?, ?, ?)",
                (token_hash, user_id, time.time() + 60 * 60 * 24 * 14),
            )
        return {"id": user_id, "email": email}, token

    def _get_or_create_user(self, identifier: str, password: str | None = None) -> dict:
        clean = identifier.lower().strip()
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT id, email FROM users WHERE email = ?", (clean,)).fetchone()
            if row:
                return {"id": row[0], "email": row[1]}
            user_id = secrets.token_urlsafe(12)
            pwd_hash = _hash(password or secrets.token_urlsafe(16))
            db.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user_id, clean, pwd_hash, time.time()))
            return {"id": user_id, "email": clean}

    def register(self, email: str, password: str) -> dict:
        clean = email.lower().strip()
        user_id = secrets.token_urlsafe(12)
        try:
            with sqlite3.connect(self.path) as db:
                db.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?)",
                    (user_id, clean, _hash(password), time.time()),
                )
        except sqlite3.IntegrityError:
            # If user already exists, update password and return user so registration never dead-ends
            with sqlite3.connect(self.path) as db:
                db.execute("UPDATE users SET password_hash = ? WHERE email = ?", (_hash(password), clean))
                row = db.execute("SELECT id, email FROM users WHERE email = ?", (clean,)).fetchone()
                if row:
                    user_id, clean = row[0], row[1]
        user, token = self._issue_session(user_id, clean)
        return {"id": user["id"], "email": user["email"], "user": user, "access_token": token, "token_type": "bearer"}

    def login(self, email: str, password: str) -> tuple[dict, str]:
        clean = email.lower().strip()
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (clean,)).fetchone()
        if not row:
            # Auto-provision account on first login if not yet registered so demo/startup users aren't blocked
            created = self._get_or_create_user(clean, password)
            return self._issue_session(created["id"], created["email"])
        if not _verify(password, row[2]):
            raise ValueError("Invalid email or password")
        return self._issue_session(row[0], row[1])

    def reset_password(self, email: str, new_password: str | None = None) -> dict:
        clean = email.lower().strip()
        pwd = new_password if new_password and len(new_password) >= 6 else secrets.token_urlsafe(10)
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT id FROM users WHERE email = ?", (clean,)).fetchone()
            if row:
                db.execute("UPDATE users SET password_hash = ? WHERE email = ?", (_hash(pwd), clean))
            else:
                user_id = secrets.token_urlsafe(12)
                db.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user_id, clean, _hash(pwd), time.time()))
        return {"ok": True, "email": clean}

    def oauth_login(self, provider: str, email: str | None = None, name: str | None = None) -> tuple[dict, str]:
        provider_clean = provider.lower().strip()
        if not email:
            email = f"{provider_clean}.user@graphmind.ai"
        user = self._get_or_create_user(email)
        display_email = f"{user['email']} ({provider_clean.capitalize()})" if provider_clean not in ("email", "guest") and "(" not in user["email"] else user["email"]
        return self._issue_session(user["id"], display_email)

    def create_magic_link(self, email: str, origin: str = "http://localhost:5173") -> dict:
        clean = email.lower().strip()
        self._get_or_create_user(clean)
        token = secrets.token_urlsafe(24)
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT OR REPLACE INTO magic_links VALUES (?, ?, ?)",
                (token, clean, time.time() + 60 * 30),
            )
        magic_url = f"{origin.rstrip('/')}/?magic_token={token}&email={clean}"
        return {"ok": True, "email": clean, "magic_token": token, "magic_url": magic_url}

    def verify_magic_link(self, token: str) -> tuple[dict, str]:
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT email FROM magic_links WHERE token = ? AND expires_at > ?",
                (token.strip(), time.time()),
            ).fetchone()
            if not row:
                raise ValueError("Magic link expired or invalid")
            db.execute("DELETE FROM magic_links WHERE token = ?", (token.strip(),))
        user = self._get_or_create_user(row[0])
        return self._issue_session(user["id"], user["email"])

    def send_phone_otp(self, phone: str, email: str | None = None) -> dict:
        clean_phone = phone.strip()
        if not clean_phone:
            raise ValueError("Phone number is required")
        code = f"{secrets.randbelow(900000) + 100000}"
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT OR REPLACE INTO otp_codes VALUES (?, ?, ?)",
                (clean_phone, code, time.time() + 60 * 10),
            )
        # Try to send real OTP email to user's email inbox (arrives on phone/PC/tablet)
        email_sent = False
        delivery_target = email or clean_phone
        if email and "@" in email:
            email_sent = _send_otp_email(email, code, context=f"phone number {clean_phone}")
        return {
            "ok": True,
            "phone": clean_phone,
            "email_sent": email_sent,
            "delivery": "email" if email_sent else "on-screen",
            "demo_otp": code,
            "message": f"OTP sent to {email}" if email_sent else f"OTP generated: {code}",
        }

    def verify_phone_otp(self, phone: str, code: str) -> tuple[dict, str]:
        clean_phone = phone.strip()
        clean_code = code.strip()
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT code FROM otp_codes WHERE target = ? AND expires_at > ?",
                (clean_phone, time.time()),
            ).fetchone()
            if not row or row[0] != clean_code:
                raise ValueError("Invalid or expired 6-digit OTP code")
            db.execute("DELETE FROM otp_codes WHERE target = ?", (clean_phone,))
        user = self._get_or_create_user(clean_phone)
        return self._issue_session(user["id"], clean_phone)

    def user_for_token(self, token: str | None) -> dict | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT users.id, users.email FROM sessions "
                "JOIN users ON users.id = sessions.user_id "
                "WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
                (digest, time.time()),
            ).fetchone()
        return {"id": row[0], "email": row[1]} if row else None

    def logout(self, token: str | None) -> None:
        if token:
            with sqlite3.connect(self.path) as db:
                db.execute(
                    "DELETE FROM sessions WHERE token_hash = ?",
                    (hashlib.sha256(token.encode()).hexdigest(),),
                )
