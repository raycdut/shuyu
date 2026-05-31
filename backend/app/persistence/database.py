"""Persistence — database connections (loaded from SQLite)."""

from __future__ import annotations

from .. import state
from ..utils.crypto import decrypt_value, encrypt_value


def load_db_connections_sqlite() -> None:
    """Load database connections from SQLite."""
    sql = state._sqlite
    if sql is None:
        state._db_connections = []
        return
    try:
        rows = sql.execute("""
            SELECT id, name, type, path, connection_string, host, port,
                   username, password, db_name, include_tables, exclude_tables, is_active, schema_status
            FROM databases ORDER BY name
        """).fetchall()
        state._db_connections = []
        for r in rows:
            state._db_connections.append({
                "id": r[0], "name": r[1], "type": r[2], "path": r[3],
                "connection_string": r[4], "host": r[5], "port": r[6],
                "user": r[7], "password": decrypt_value(r[8]), "database": r[9],
                "include_tables": r[10].split(",") if r[10] else None,
                "exclude_tables": r[11].split(",") if r[11] else None,
                "is_active": bool(r[12]),
                "schema_status": r[13] or "pending",
            })
    except Exception:
        state._db_connections = []


def save_db_connections_sqlite() -> None:
    """Save database connections to SQLite — uses REPLACE for safety."""
    sql = state._sqlite
    if sql is None:
        return
    try:
        seen = set()
        for db in state._db_connections:
            db_id = db["id"]
            sql.execute(
                "INSERT OR REPLACE INTO databases "
                "(id, name, type, path, connection_string, host, port, "
                "username, password, db_name, include_tables, exclude_tables, is_active) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    db_id, db["name"], db.get("type", "duckdb"), db.get("path"),
                    db.get("connection_string"), db.get("host"), db.get("port"),
                    db.get("user"), encrypt_value(db.get("password")), db.get("database"),
                    ",".join(db.get("include_tables") or []),
                    ",".join(db.get("exclude_tables") or []),
                    1 if db.get("is_active") else 0,
                ),
            )
            seen.add(db_id)
        # Remove stale entries
        existing = sql.execute("SELECT id FROM databases").fetchall()
        for (eid,) in existing:
            if eid not in seen:
                sql.execute("DELETE FROM databases WHERE id = ?", (eid,))
        sql.commit()
    except Exception:
        pass
