from __future__ import annotations

import logging
import os
import sqlite3
import secrets
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
    env_secret = os.environ.get("AUTH_SECRET_KEY")
    if env_secret:
        SECRET_KEY = env_secret
    else:
        SECRET_KEY = secrets.token_urlsafe(48)
        logging.getLogger("shuyu.main").warning(
            "AUTH_SECRET_KEY 未设置，已生成临时密钥（仅当前进程有效）。生产环境请配置 AUTH_SECRET_KEY。"
        )
    ALGORITHM = "HS256"
    EXPIRE_MINUTES = int(os.environ.get("AUTH_EXPIRE_MINUTES", "1440"))


def _get_db() -> sqlite3.Connection:
    if state._sqlite is None:
        raise RuntimeError("Database not initialized")
    return state._sqlite


def create_user(username: str, password: str, changed_by: str | None = None) -> dict:
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

    from ..admin_config.service import log_user_management_change
    log_user_management_change(
        changed_by or username,
        f"创建用户: {username} (角色: {role})",
        target_user_id=user_id,
    )

    return {"id": user_id, "username": username, "role": role, "is_active": True, "created_at": now, "last_login_at": None}


def authenticate_user(username: str, password: str) -> dict | None:
    db = _get_db()
    row = db.execute(
        "SELECT id, username, password_hash, role, is_active, created_at, last_login_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if not row:
        return None
    user_id, uname, pw_hash, role, is_active, created_at, last_login_at = row
    if not is_active:
        return None
    if not bcrypt.checkpw(password.encode(), pw_hash.encode()):
        return None
    return {"id": user_id, "username": uname, "role": role, "is_active": bool(is_active), "created_at": created_at, "last_login_at": last_login_at}


def get_user_by_id(user_id: str) -> dict | None:
    db = _get_db()
    row = db.execute(
        "SELECT id, username, role, is_active, created_at, last_login_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return None
    return {"id": row[0], "username": row[1], "role": row[2], "is_active": bool(row[3]), "created_at": row[4], "last_login_at": row[5]}


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


def update_last_login(user_id: str) -> None:
    """Update the last_login_at timestamp for the given user to the current time."""
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, user_id))
    db.commit()


def get_all_users() -> list[dict]:
    db = _get_db()
    rows = db.execute(
        "SELECT id, username, role, is_active, created_at, last_login_at FROM users ORDER BY created_at ASC"
    ).fetchall()
    return [
        {"id": r[0], "username": r[1], "role": r[2], "is_active": bool(r[3]), "created_at": r[4], "last_login_at": r[5]}
        for r in rows
    ]


def update_user(user_id: str, role: str | None = None, is_active: bool | None = None, changed_by: str | None = None) -> dict | None:
    db = _get_db()
    old_user = get_user_by_id(user_id)
    fields = []
    values = []
    changes = []
    if role is not None:
        fields.append("role = ?")
        values.append(role)
        old_role = old_user["role"] if old_user else "?"
        changes.append(f"角色: {old_role}→{role}")
    if is_active is not None:
        fields.append("is_active = ?")
        values.append(1 if is_active else 0)
        old_active = old_user["is_active"] if old_user else "?"
        changes.append(f"状态: {'启用' if old_active else '禁用'}→{'启用' if is_active else '禁用'}")
    if not fields:
        return get_user_by_id(user_id)
    values.append(datetime.now(timezone.utc).isoformat())
    values.append(user_id)
    db.execute(f"UPDATE users SET {', '.join(fields)}, updated_at = ? WHERE id = ?", values)
    db.commit()

    from ..admin_config.service import log_user_management_change
    username = old_user["username"] if old_user else user_id
    log_user_management_change(
        changed_by or "unknown",
        f"更新用户: {username} — {'; '.join(changes)}",
        target_user_id=user_id,
    )

    return get_user_by_id(user_id)


def delete_user(user_id: str, changed_by: str | None = None) -> bool:
    db = _get_db()
    old_user = get_user_by_id(user_id)
    # Cascade delete user's sessions and messages
    try:
        db.execute("DELETE FROM messages WHERE session_id IN (SELECT id FROM sessions WHERE user_id = ?)", (user_id,))
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    except sqlite3.OperationalError:
        pass
    cursor = db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    deleted = cursor.rowcount > 0
    if deleted:
        from ..admin_config.service import log_user_management_change
        username = old_user["username"] if old_user else user_id
        log_user_management_change(
            changed_by or "unknown",
            f"删除用户: {username}",
            target_user_id=user_id,
        )
    return deleted


def get_user_databases(user_id: str) -> list[str]:
    db = _get_db()
    rows = db.execute(
        "SELECT database_id FROM user_databases WHERE user_id = ?", (user_id,)
    ).fetchall()
    return [r[0] for r in rows]


def set_user_databases(user_id: str, database_ids: list[str], changed_by: str | None = None):
    db = _get_db()
    db.execute("DELETE FROM user_databases WHERE user_id = ?", (user_id,))
    for db_id in database_ids:
        db.execute(
            "INSERT INTO user_databases (user_id, database_id) VALUES (?, ?)",
            (user_id, db_id),
        )
    db.commit()

    from ..admin_config.service import log_user_management_change
    user = get_user_by_id(user_id)
    username = user["username"] if user else user_id
    log_user_management_change(
        changed_by or "unknown",
        f"为用户 {username} 分配 {len(database_ids)} 个数据库权限",
        target_user_id=user_id,
    )
