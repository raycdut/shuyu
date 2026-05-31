"""Create the initial admin user.

This script creates the first admin user in the database.
If a user with the same username already exists, it will skip creation.

Usage:
    python seeds/create_admin.py                          # interactive mode
    python seeds/create_admin.py --username admin --password mypass  # CLI mode
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import bcrypt
except ImportError:
    bcrypt = None  # type: ignore[assignment]


SEEDS_DIR = Path(__file__).resolve().parent
DB_PATH = SEEDS_DIR.parent / "data" / "config.db"


def _get_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        print("Make sure the backend server has been started at least once to initialize the database.")
        sys.exit(1)
    return sqlite3.connect(str(DB_PATH))


def user_exists(db: sqlite3.Connection, username: str) -> bool:
    row = db.execute("SELECT COUNT(*) FROM users WHERE username = ?", (username,)).fetchone()
    return row is not None and row[0] > 0


def create_admin_user(db: sqlite3.Connection, username: str, password: str) -> dict:
    if not bcrypt:
        print("Error: bcrypt module is required. Install it with: pip install bcrypt")
        sys.exit(1)

    user_id = str(uuid.uuid4())
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    now = datetime.now(timezone.utc).isoformat()

    db.execute(
        "INSERT INTO users (id, username, password_hash, role, is_active, created_at, updated_at) VALUES (?, ?, ?, 'admin', 1, ?, ?)",
        (user_id, username, password_hash, now, now),
    )
    db.commit()

    log_user_change(db, username, f"创建初始管理员: {username}")
    return {"id": user_id, "username": username, "role": "admin"}


def log_user_change(db: sqlite3.Connection, changed_by: str, summary: str):
    try:
        db.execute(
            "INSERT INTO config_changelog (config_type, user_id, changed_by, summary, created_at) VALUES ('user_mgmt', NULL, ?, ?, ?)",
            (changed_by, summary, datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
    except Exception:
        pass  # config_changelog table might not exist yet


def interactive():
    """Interactive prompt for username and password."""
    db = _get_db()

    # Check existing users
    existing = db.execute("SELECT username, role FROM users ORDER BY created_at ASC").fetchall()
    if existing:
        print("Existing users in database:")
        for uname, role in existing:
            print(f"  - {uname} ({role})")
        print()

    username = input("Admin username [admin]: ").strip() or "admin"
    if user_exists(db, username):
        print(f"User '{username}' already exists. Skipping.")
        sys.exit(0)

    password = input("Admin password (min 6 chars): ").strip()
    if len(password) < 6:
        print("Password must be at least 6 characters.")
        sys.exit(1)

    confirm = input("Confirm password: ").strip()
    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)

    result = create_admin_user(db, username, password)
    print(f"Admin user created: {result['username']} (role: {result['role']})")


def cli(username: str, password: str):
    db = _get_db()
    if len(password) < 6:
        print("Password must be at least 6 characters.")
        sys.exit(1)
    if user_exists(db, username):
        print(f"User '{username}' already exists. Skipping.")
        return
    result = create_admin_user(db, username, password)
    print(f"Admin user created: {result['username']} (role: {result['role']})")


def main():
    parser = argparse.ArgumentParser(description="Create the initial admin user")
    parser.add_argument("--username", help="Admin username")
    parser.add_argument("--password", help="Admin password")
    args = parser.parse_args()

    if args.username and args.password:
        cli(args.username, args.password)
    else:
        interactive()


if __name__ == "__main__":
    main()
