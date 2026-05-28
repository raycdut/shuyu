"""Session manager — handles multi-turn conversation memory with SQLite persistence.

Uses sliding window + summary compression (same pattern as Hermes hot memory).
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any

MAX_MESSAGES = 20
KEEP_RECENT = 6


class Session:
    """A single conversation session, persisted to SQLite."""

    def __init__(self, session_id: str, title: str = "", sqlite: sqlite3.Connection | None = None):
        self.session_id = session_id
        self.created_at = time.time()
        self.last_active = time.time()
        self.messages: list[dict] = []
        self.summary: str = ""
        self.metadata: dict[str, Any] = {"title": title}
        self._title = title or ""
        self._sqlite = sqlite

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str):
        self._title = value
        self.metadata["title"] = value
        if self._sqlite:
            self._sqlite.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (value, time.time(), self.session_id),
            )
            self._sqlite.commit()

    def add_message(self, role: str, content: str, tool_calls: list = None) -> None:
        self.last_active = time.time()
        msg = {"role": role, "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)
        self._maybe_compress()

        # Persist to SQLite
        if self._sqlite:
            self._sqlite.execute(
                "INSERT OR IGNORE INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (self.session_id, self._title, self.created_at, self.last_active),
            )
            self._sqlite.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (self.session_id, role, content, time.time()),
            )
            self._sqlite.commit()

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self.last_active = time.time()
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })

    def get_messages(self) -> list[dict]:
        result = list(self.messages)
        if self.summary:
            result = [
                {"role": "system", "content": f"对话摘要（已有对话的压缩版本）：{self.summary}"}
            ] + result
        return result

    def _maybe_compress(self) -> None:
        user_assistant_count = sum(
            1 for m in self.messages if m["role"] in ("user", "assistant")
        )
        if user_assistant_count <= MAX_MESSAGES:
            return

        old_messages = self.messages[:-(KEEP_RECENT * 2)]
        summary_parts = []
        for m in old_messages:
            if m["role"] == "user":
                summary_parts.append(f"用户说: {m['content'][:200]}")
            elif m["role"] == "assistant":
                summary_parts.append(f"助手回答: {m['content'][:200]}")
            elif m["role"] == "tool" and "error" in m.get("content", "").lower():
                summary_parts.append(f"工具出错: {m['content'][:200]}")
        self.summary = "\n".join(summary_parts)
        self.messages = self.messages[-(KEEP_RECENT * 2):]


class SessionManager:
    """Manages all active sessions, backed by SQLite."""

    def __init__(self, sqlite_conn: sqlite3.Connection | None = None):
        self._sqlite = sqlite_conn
        self._sessions: dict[str, Session] = {}
        self._timeout: int = 3600  # 1 hour

        # Load existing sessions from SQLite
        if self._sqlite:
            try:
                rows = self._sqlite.execute(
                    "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
                ).fetchall()
                for sid, title, created, updated in rows:
                    sess = Session(sid, title or "", self._sqlite)
                    sess.created_at = created
                    sess.last_active = updated
                    # Load messages
                    msgs = self._sqlite.execute(
                        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
                        (sid,),
                    ).fetchall()
                    for role, content in msgs:
                        sess.messages.append({"role": role, "content": content})
                    # Auto-title from first user message
                    for m in sess.messages:
                        if m["role"] == "user" and not title:
                            sess.title = m["content"][:30] + ("…" if len(m["content"]) > 30 else "")
                            break
                    self._sessions[sid] = sess
            except Exception:
                pass

    def get_or_create(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id, sqlite=self._sqlite)
        return self._sessions[session_id]

    def delete(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]
        if self._sqlite:
            self._sqlite.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self._sqlite.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self._sqlite.commit()

    def rename(self, session_id: str, title: str) -> None:
        sess = self._sessions.get(session_id)
        if sess:
            sess.title = title

    def cleanup_expired(self) -> None:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_active > self._timeout
        ]
        for sid in expired:
            self.delete(sid)
