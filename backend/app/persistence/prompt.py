"""Persistence — prompt versions."""

from __future__ import annotations

import time

from .. import state


def load_active_prompt() -> str | None:
    """Load the active system prompt from SQLite."""
    sql = state._sqlite
    if sql is None:
        return None
    row = sql.execute(
        "SELECT content FROM prompts WHERE is_active = 1 ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def create_prompt_version(name: str, content: str) -> dict:
    """Create a new prompt version (deactivates old ones)."""
    sql = state._sqlite
    if sql is None:
        return {"ok": False, "error": "no db"}

    row = sql.execute("SELECT MAX(version) FROM prompts WHERE name = ?", (name,)).fetchone()
    new_version = (row[0] or 0) + 1

    sql.execute("UPDATE prompts SET is_active = 0 WHERE name = ?", (name,))
    sql.execute(
        "INSERT INTO prompts (name, content, version, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
        (name, content, new_version, time.time()),
    )
    sql.commit()
    return {"ok": True, "version": new_version}
