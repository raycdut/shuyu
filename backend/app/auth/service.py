"""Authentication service — user management via SQLAlchemy ORM."""

from __future__ import annotations

import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .. import state
from ..configdb.base import scoped_session
from ..configdb.models.user import User, UserDatabase
from ..configdb.models.session import Session

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


def create_user(username: str, password: str, changed_by: str | None = None) -> dict:
    with scoped_session() as session:
        existing = session.query(User).filter_by(username=username).first()
        if existing:
            raise ValueError("用户名已存在")

        user_count = session.query(User).count()
        role = "admin" if user_count == 0 else "user"

        user_id = str(uuid.uuid4())
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        now = datetime.now(timezone.utc).isoformat()

        user = User(
            id=user_id,
            username=username,
            password_hash=password_hash,
            role=role,
            created_at=now,
            updated_at=now,
        )
        session.add(user)

    from ..admin_config.service import log_user_management_change
    log_user_management_change(
        changed_by or username,
        f"创建用户: {username} (角色: {role})",
        target_user_id=user_id,
    )

    return {"id": user_id, "username": username, "role": role, "is_active": True, "created_at": now, "last_login_at": None}


def authenticate_user(username: str, password: str) -> dict | None:
    with scoped_session() as session:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return None
        if not user.is_active:
            return None
        if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            return None
        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if hasattr(user.created_at, 'isoformat') else str(user.created_at),
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at and hasattr(user.last_login_at, 'isoformat') else str(user.last_login_at or ""),
        }


def get_user_by_id(user_id: str) -> dict | None:
    with scoped_session() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return None
        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if hasattr(user.created_at, 'isoformat') else str(user.created_at),
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at and hasattr(user.last_login_at, 'isoformat') else str(user.last_login_at or ""),
        }


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
    now = datetime.now(timezone.utc).isoformat()
    with scoped_session() as session:
        session.query(User).filter_by(id=user_id).update({"last_login_at": now})


def get_all_users() -> list[dict]:
    with scoped_session() as session:
        users = session.query(User).order_by(User.created_at).all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if hasattr(u.created_at, 'isoformat') else str(u.created_at),
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at and hasattr(u.last_login_at, 'isoformat') else str(u.last_login_at or ""),
            }
            for u in users
        ]


def update_user(user_id: str, role: str | None = None, is_active: bool | None = None, changed_by: str | None = None) -> dict | None:
    old_user = get_user_by_id(user_id)
    changes = []

    with scoped_session() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return None

        if role is not None:
            old_role = old_user["role"] if old_user else "?"
            changes.append(f"角色: {old_role}→{role}")
            user.role = role
        if is_active is not None:
            old_active = old_user["is_active"] if old_user else "?"
            changes.append(f"状态: {'启用' if old_active else '禁用'}→{'启用' if is_active else '禁用'}")
            user.is_active = is_active
        user.updated_at = datetime.now(timezone.utc).isoformat()

    if changes:
        from ..admin_config.service import log_user_management_change
        username = old_user["username"] if old_user else user_id
        log_user_management_change(
            changed_by or "unknown",
            f"更新用户: {username} — {'; '.join(changes)}",
            target_user_id=user_id,
        )

    return get_user_by_id(user_id)


def delete_user(user_id: str, changed_by: str | None = None) -> bool:
    old_user = get_user_by_id(user_id)
    with scoped_session() as session:
        # Cascade delete user's sessions and messages
        session.query(Session).filter_by(user_id=user_id).delete()
        result = session.query(User).filter_by(id=user_id).delete()

    deleted = result > 0
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
    with scoped_session() as session:
        rows = session.query(UserDatabase).filter_by(user_id=user_id).all()
        return [r.database_id for r in rows]


def set_user_databases(user_id: str, database_ids: list[str], changed_by: str | None = None):
    with scoped_session() as session:
        session.query(UserDatabase).filter_by(user_id=user_id).delete()
        for db_id in database_ids:
            session.add(UserDatabase(user_id=user_id, database_id=db_id))

    from ..admin_config.service import log_user_management_change
    user = get_user_by_id(user_id)
    username = user["username"] if user else user_id
    log_user_management_change(
        changed_by or "unknown",
        f"为用户 {username} 分配 {len(database_ids)} 个数据库权限",
        target_user_id=user_id,
    )
