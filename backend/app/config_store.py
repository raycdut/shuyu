"""SQLite persistence for config, database connections, and sessions."""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

from . import state

logger = logging.getLogger("shuyu.main")


# ======================================================================
# Init
# ======================================================================


def init_sqlite():
    """Initialize SQLite database with schema."""
    logger.info(f"Initializing SQLite: {state.config.storage.path}")
    db_path = Path(state.config.storage.path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    state._sqlite = sqlite3.connect(str(db_path))
    state._sqlite.execute("PRAGMA journal_mode=WAL")
    state._sqlite.execute("PRAGMA busy_timeout=5000")

    state._sqlite.executescript("""
        CREATE TABLE IF NOT EXISTS llm_providers (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            provider   TEXT NOT NULL DEFAULT 'openai',
            model      TEXT NOT NULL DEFAULT 'gpt-4o',
            api_key    TEXT DEFAULT '',
            api_base   TEXT DEFAULT '',
            is_active  INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        INSERT OR IGNORE INTO settings (key, value) VALUES ('safety_read_only', 'true');
        INSERT OR IGNORE INTO settings (key, value) VALUES ('safety_max_rows', '1000');

        CREATE TABLE IF NOT EXISTS databases (
            id                TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            type              TEXT NOT NULL DEFAULT 'duckdb',
            path              TEXT,
            connection_string TEXT,
            host              TEXT,
            port              INTEGER,
            username          TEXT,
            password          TEXT,
            db_name           TEXT,
            include_tables    TEXT,
            exclude_tables    TEXT,
            is_active         INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id         TEXT PRIMARY KEY,
            title      TEXT DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            role      TEXT NOT NULL,
            content   TEXT NOT NULL DEFAULT '',
            tool_data TEXT,
            created_at REAL NOT NULL
        );
    """)


# ======================================================================
# Config load / save
# ======================================================================


def load_config_sqlite():
    """Load config from SQLite into runtime config object."""
    sql = state._sqlite
    if sql is None:
        return
    try:
        _migrate_old_config()

        row = sql.execute(
            "SELECT provider, model, api_key, api_base FROM llm_providers WHERE is_active = 1"
        ).fetchone()
        if row:
            state.config.llm.provider = row[0] or "openai"
            state.config.llm.model = row[1] or "gpt-4o"
            state.config.llm.api_key = row[2] or ""
            state.config.llm.api_base = row[3] or ""

        rows = sql.execute("SELECT key, value FROM settings").fetchall()
        for key, value in rows:
            if key == "safety_read_only":
                state.config.safety.read_only = value == "true"
            elif key == "safety_max_rows":
                state.config.safety.max_rows = int(value)
    except Exception:
        pass


def save_config_sqlite():
    """Save runtime config to SQLite."""
    sql = state._sqlite
    if sql is None:
        return
    try:
        logger.info(f"Saving config: LLM={state.config.llm.provider}/{state.config.llm.model}")
        existing = sql.execute(
            "SELECT id FROM llm_providers WHERE is_active = 1"
        ).fetchone()
        if existing:
            sql.execute(
                "UPDATE llm_providers SET provider=?, model=?, api_key=?, api_base=? WHERE id=?",
                (state.config.llm.provider, state.config.llm.model,
                 state.config.llm.api_key, state.config.llm.api_base or "", existing[0]),
            )
        else:
            sql.execute(
                "INSERT INTO llm_providers (name, provider, model, api_key, api_base, is_active, created_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?)",
                (state.config.llm.provider, state.config.llm.provider, state.config.llm.model,
                 state.config.llm.api_key, state.config.llm.api_base or "", time.time()),
            )

        sql.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    ("safety_read_only", str(state.config.safety.read_only).lower()))
        sql.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    ("safety_max_rows", str(state.config.safety.max_rows)))
        sql.commit()
    except Exception:
        pass


def _migrate_old_config():
    """Migrate from old key-value config table to new schema."""
    sql = state._sqlite
    if sql is None:
        return
    try:
        old = sql.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='config'"
        ).fetchone()
        if not old:
            return
        logger.info("Old config table found, migrating to new schema...")

        rows = sql.execute("SELECT key, value FROM config").fetchall()
        if not rows:
            return

        pairs = dict(rows)
        has_llm = "llm_provider" in pairs or "llm_model" in pairs

        if has_llm:
            existing_active = sql.execute(
                "SELECT id FROM llm_providers WHERE is_active = 1"
            ).fetchone()
            if existing_active:
                sql.execute("DROP TABLE IF EXISTS config")
                sql.commit()
                return

            sql.execute(
                "INSERT INTO llm_providers (name, provider, model, api_key, api_base, is_active, created_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?)",
                (pairs.get("llm_provider", "default"), pairs.get("llm_provider", "openai"),
                 pairs.get("llm_model", "gpt-4o"), pairs.get("llm_api_key", ""),
                 pairs.get("llm_api_base", ""), time.time()),
            )

            for old_key, new_key in [("safety_read_only", "safety_read_only"),
                                      ("safety_max_rows", "safety_max_rows")]:
                if old_key in pairs:
                    sql.execute(
                        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                        (new_key, pairs[old_key]),
                    )

        sql.execute("DROP TABLE IF EXISTS config")
        sql.commit()
    except Exception:
        pass


# ======================================================================
# Database connections load / save
# ======================================================================


def load_db_connections_sqlite():
    """Load database connections from SQLite."""
    sql = state._sqlite
    if sql is None:
        state._db_connections = []
        return
    try:
        rows = sql.execute("""
            SELECT id, name, type, path, connection_string, host, port,
                   username, db_name, include_tables, exclude_tables, is_active
            FROM databases ORDER BY name
        """).fetchall()
        state._db_connections = []
        for r in rows:
            state._db_connections.append({
                "id": r[0], "name": r[1], "type": r[2], "path": r[3],
                "connection_string": r[4], "host": r[5], "port": r[6],
                "user": r[7], "database": r[8],
                "include_tables": r[9].split(",") if r[9] else None,
                "exclude_tables": r[10].split(",") if r[10] else None,
                "is_active": bool(r[11]),
            })
    except Exception:
        state._db_connections = []


def save_db_connections_sqlite():
    """Save database connections to SQLite."""
    sql = state._sqlite
    if sql is None:
        return
    sql.execute("DELETE FROM databases")
    for db in state._db_connections:
        sql.execute(
            "INSERT INTO databases (id, name, type, path, connection_string, host, port, "
            "username, password, db_name, include_tables, exclude_tables, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                db["id"], db["name"], db["type"], db.get("path"),
                db.get("connection_string"), db.get("host"), db.get("port"),
                db.get("user"), db.get("password"), db.get("database"),
                ",".join(db.get("include_tables") or []),
                ",".join(db.get("exclude_tables") or []),
                1 if db.get("is_active") else 0,
            ),
        )
    sql.commit()
