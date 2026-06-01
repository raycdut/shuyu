"""Persistence — database connections (loaded from ConfigDB)."""

from __future__ import annotations

from .. import state
from ..configdb.base import scoped_session
from ..configdb.models.database import DatabaseConnection
from ..utils.crypto import decrypt_value, encrypt_value


def load_db_connections_sqlite() -> None:
    """Load database connections from ConfigDB."""
    try:
        with scoped_session() as session:
            rows = session.query(DatabaseConnection).order_by(DatabaseConnection.name).all()
            state._db_connections = []
            for r in rows:
                state._db_connections.append({
                    "id": r.id,
                    "name": r.name,
                    "type": r.type,
                    "path": r.path,
                    "connection_string": r.connection_string,
                    "host": r.host,
                    "port": r.port,
                    "user": r.username,
                    "password": decrypt_value(r.password) if r.password else "",
                    "database": r.db_name,
                    "include_tables": r.include_tables.split(",") if r.include_tables else None,
                    "exclude_tables": r.exclude_tables.split(",") if r.exclude_tables else None,
                    "is_active": bool(r.is_active),
                    "schema_status": r.schema_status or "pending",
                })
    except Exception:
        state._db_connections = []


def save_db_connections_sqlite() -> None:
    """Save database connections to ConfigDB."""
    try:
        with scoped_session() as session:
            seen = set()
            for db in state._db_connections:
                db_id = db["id"]
                row = session.query(DatabaseConnection).filter_by(id=db_id).first()
                if row:
                    row.name = db["name"]
                    row.type = db.get("type", "duckdb")
                    row.path = db.get("path")
                    row.connection_string = db.get("connection_string")
                    row.host = db.get("host")
                    row.port = db.get("port")
                    row.username = db.get("user")
                    row.password = encrypt_value(db.get("password"))
                    row.db_name = db.get("database")
                    row.include_tables = ",".join(db.get("include_tables") or [])
                    row.exclude_tables = ",".join(db.get("exclude_tables") or [])
                    row.is_active = 1 if db.get("is_active") else 0
                else:
                    session.add(DatabaseConnection(
                        id=db_id,
                        name=db["name"],
                        type=db.get("type", "duckdb"),
                        path=db.get("path"),
                        connection_string=db.get("connection_string"),
                        host=db.get("host"),
                        port=db.get("port"),
                        username=db.get("user"),
                        password=encrypt_value(db.get("password")),
                        db_name=db.get("database"),
                        include_tables=",".join(db.get("include_tables") or []),
                        exclude_tables=",".join(db.get("exclude_tables") or []),
                        is_active=1 if db.get("is_active") else 0,
                    ))
                seen.add(db_id)
            # Remove stale entries
            existing = session.query(DatabaseConnection).all()
            for row in existing:
                if row.id not in seen:
                    session.delete(row)
    except Exception:
        pass
