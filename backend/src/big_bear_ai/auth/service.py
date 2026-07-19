from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import bcrypt
import psycopg
from jose import JWTError, jwt


ROOT = Path(__file__).resolve().parents[4]
SQLITE_PATH = ROOT / "runtime" / "auth.db"
TOKEN_TTL_DAYS = 30


def runtime_name() -> str:
    return os.environ.get("BIG_BEAR_RUNTIME", "inmem")


def auth_secret() -> str:
    secret = os.environ.get("AUTH_DEV_SECRET")
    if not secret:
        raise RuntimeError("AUTH_DEV_SECRET must be configured")
    return secret


def password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def password_matches(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8")[:72], hashed_password.encode("utf-8"))


def issue_token(user: dict[str, Any]) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "iat": now,
        "exp": now + timedelta(days=TOKEN_TTL_DAYS),
    }
    audience = os.environ.get("AUTH_AUDIENCE")
    if audience:
        payload["aud"] = audience
    return jwt.encode(payload, auth_secret(), algorithm="HS256")


def verify_token(authorization: str | None) -> dict[str, Any]:
    if not authorization:
        raise ValueError("Missing authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ValueError("Authorization must use a Bearer token")
    options = {"verify_aud": bool(os.environ.get("AUTH_AUDIENCE"))}
    try:
        return jwt.decode(
            token,
            auth_secret(),
            algorithms=["HS256"],
            audience=os.environ.get("AUTH_AUDIENCE"),
            options=options,
        )
    except JWTError as error:
        raise ValueError("Invalid or expired access token") from error


def initialize_users() -> None:
    if runtime_name() == "postgres":
        return
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(SQLITE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login_at TEXT
            )
            """
        )


def register_user(username: str, email: str, password: str, display_name: str | None) -> dict[str, Any]:
    initialize_users()
    user = {
        "id": str(uuid.uuid4()),
        "username": username,
        "email": email,
        "password_hash": password_hash(password),
        "display_name": display_name or username,
        "role": "user",
        "is_active": True,
        "created_at": datetime.now(UTC).isoformat(),
    }
    if runtime_name() == "postgres":
        return _postgres_register(user)
    return _sqlite_register(user)


def authenticate_user(username: str, password: str) -> dict[str, Any]:
    initialize_users()
    user = _postgres_by_username(username) if runtime_name() == "postgres" else _sqlite_by_username(username)
    if user is None or not user["is_active"] or not password_matches(password, user["password_hash"]):
        raise ValueError("Invalid username or password")
    _record_login(user["id"])
    return user


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {key: user[key] for key in ("id", "username", "email", "display_name", "role", "is_active", "created_at")}


def _sqlite_register(user: dict[str, Any]) -> dict[str, Any]:
    try:
        with sqlite3.connect(SQLITE_PATH) as connection:
            connection.execute(
                "INSERT INTO users (id, username, email, password_hash, display_name, role, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(user[key] for key in ("id", "username", "email", "password_hash", "display_name", "role", "is_active", "created_at")),
            )
    except sqlite3.IntegrityError as error:
        raise ValueError("Username or email already registered") from error
    return user


def _sqlite_by_username(username: str) -> dict[str, Any] | None:
    with sqlite3.connect(SQLITE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def _postgres_register(user: dict[str, Any]) -> dict[str, Any]:
    try:
        with psycopg.connect(os.environ["DATABASE_URI"]) as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (id, username, email, password_hash, display_name, role, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                tuple(user[key] for key in ("id", "username", "email", "password_hash", "display_name", "role", "is_active")),
            )
    except psycopg.errors.UniqueViolation as error:
        raise ValueError("Username or email already registered") from error
    return user


def _postgres_by_username(username: str) -> dict[str, Any] | None:
    with psycopg.connect(os.environ["DATABASE_URI"], row_factory=psycopg.rows.dict_row) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cursor.fetchone()


def _record_login(user_id: str) -> None:
    if runtime_name() == "postgres":
        with psycopg.connect(os.environ["DATABASE_URI"]) as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (user_id,))
        return
    with sqlite3.connect(SQLITE_PATH) as connection:
        connection.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (datetime.now(UTC).isoformat(), user_id))