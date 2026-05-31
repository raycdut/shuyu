"""Migration 003: Add last_login_at column to users table."""

from __future__ import annotations

import sqlite3


def migrate_last_login(conn: sqlite3.Connection) -> None:
    """Add last_login_at column to users table if not already present."""
    cursor = conn.cursor()
    columns = [col[1] for col in cursor.execute("PRAGMA table_info(users)").fetchall()]
    if "last_login_at" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN last_login_at TEXT")
        conn.commit()
