"""Shared test fixtures — initialize ConfigDB (file-based temp SQLite)."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def setup_configdb():
    """Initialize the ConfigDB with a temporary file-based SQLite database.

    Uses a temp file so that the SQLAlchemy engine and the raw ``state._sqlite``
    connection can both access the same database.
    """
    from app import state
    from app.config import Config
    from app.configdb import init_configdb

    state.config = Config()
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    init_configdb(f"sqlite:///{db_path}?check_same_thread=False")

    # Backward-compat raw connection to the SAME database file
    state._sqlite = sqlite3.connect(db_path, check_same_thread=False)
    state._sqlite.execute("PRAGMA journal_mode=WAL")
    state._sqlite.execute("PRAGMA foreign_keys=ON")

    state._db_connections = []
    yield

    if state._sqlite:
        state._sqlite.close()
    if state._configdb_engine:
        state._configdb_engine.dispose()
    state._configdb_engine = None
    state._configdb_session_factory = None
    state._sqlite = None
    try:
        os.unlink(db_path)
    except OSError:
        pass
