"""Migration 004: Expand config_changelog config_type CHECK constraint."""
from __future__ import annotations

import sqlite3


def migrate_config_type(conn: sqlite3.Connection) -> None:
    """Recreate config_changelog table with expanded config_type CHECK constraint.
    
    New valid types: 'system', 'user', 'user_mgmt', 'database'
    """
    cursor = conn.cursor()
    columns = [col[1] for col in cursor.execute("PRAGMA table_info(config_changelog)").fetchall()]
    if not columns:
        return
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS config_changelog_new (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            config_type TEXT NOT NULL CHECK (config_type IN ('system', 'user', 'user_mgmt', 'database')),
            user_id     TEXT,
            changed_by  TEXT NOT NULL,
            summary     TEXT NOT NULL,
            diff        TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO config_changelog_new (id, config_type, user_id, changed_by, summary, diff, created_at)
            SELECT id, config_type, user_id, changed_by, summary, diff, created_at FROM config_changelog;
        DROP TABLE config_changelog;
        ALTER TABLE config_changelog_new RENAME TO config_changelog;
    """)
    conn.commit()
