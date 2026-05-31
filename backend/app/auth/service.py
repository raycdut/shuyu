from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .. import state

SECRET_KEY: str = ""
ALGORITHM: str = "HS256"
EXPIRE_MINUTES: int = 1440


def init_auth_config():
    global SECRET_KEY, ALGORITHM, EXPIRE_MINUTES
    import os
    SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", "change-me-to-a-random-secret")
    ALGORITHM = "HS256"
    EXPIRE_MINUTES = int(os.environ.get("AUTH_EXPIRE_MINUTES", "1440"))


def _get_db() -> sqlite3.Connection:
    if state._sqlite is None:
        raise RuntimeError("Database not initialized")
    return state._sqlite


def create_user(username: str, password: str) -> dict:
    db = _get_db()
    cursor = db.cursor()

    existing = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        raise ValueError("用户名已存在")

    user_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    role = "admin" if user_count == 0 else "user"

    user_id = str(uuid.uuid4())
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    now = datetime.now(timezone.utc).isoformat()

    cursor.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, username, password_hash, role, now, now),
    )
    db.commit()

    return {"id": user_id, "username": username, "role": role, "is_active": True, "created_at": now}


def authenticate_user(username: str, password: str) -> dict | None:
    db = _get_db()
    row = db.execute(
        "SELECT id, username, password_hash, role, is_active, created_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if not row:
        return None
    user_id, uname, pw_hash, role, is_active, created_at = row
    if not is_active:
        return None
    if not bcrypt.checkpw(password.encode(), pw_hash.encode()):
        return None
    return {"id": user_id, "username": uname, "role": role, "is_active": bool(is_active), "created_at": created_at}


def get_user_by_id(user_id: str) -> dict | None:
    db = _get_db()
    row = db.execute(
        "SELECT id, username, role, is_active, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return None
    return {"id": row[0], "username": row[1], "role": row[2], "is_active": bool(row[3]), "created_at": row[4]}


def create_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_all_users() -> list[dict]:
    db = _get_db()
    rows = db.execute(
        "SELECT id, username, role, is_active, created_at FROM users ORDER BY created_at ASC"
    ).fetchall()
    return [
        {"id": r[0], "username": r[1], "role": r[2], "is_active": bool(r[3]), "created_at": r[4]}
        for r in rows
    ]


def update_user(user_id: str, role: str | None = None, is_active: bool | None = None) -> dict | None:
    db = _get_db()
    fields = []
    values = []
    if role is not None:
        fields.append("role = ?")
        values.append(role)
    if is_active is not None:
        fields.append("is_active = ?")
        values.append(1 if is_active else 0)
    if not fields:
        return get_user_by_id(user_id)
    values.append(datetime.now(timezone.utc).isoformat())
    values.append(user_id)
    db.execute(f"UPDATE users SET {', '.join(fields)}, updated_at = ? WHERE id = ?", values)
    db.commit()
    return get_user_by_id(user_id)


def delete_user(user_id: str) -> bool:
    db = _get_db()
    cursor = db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return cursor.rowcount > 0


def get_user_databases(user_id: str) -> list[str]:
    db = _get_db()
    rows = db.execute(
        "SELECT database_id FROM user_databases WHERE user_id = ?", (user_id,)
    ).fetchall()
    return [r[0] for r in rows]


def set_user_databases(user_id: str, database_ids: list[str]):
    db = _get_db()
    db.execute("DELETE FROM user_databases WHERE user_id = ?", (user_id,))
    for db_id in database_ids:
        db.execute(
            "INSERT INTO user_databases (user_id, database_id) VALUES (?, ?)",
            (user_id, db_id),
        )
    db.commit()
