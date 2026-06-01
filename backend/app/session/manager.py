"""Session manager — handles multi-turn conversation memory with ConfigDB persistence.

Uses sliding window + summary compression (same pattern as Hermes hot memory).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..configdb.base import scoped_session
from ..configdb.models.session import Session as SessionModel, Message

logger = logging.getLogger("shuyu.session")

MAX_MESSAGES = 20
KEEP_RECENT = 6


class Session:
    """A single conversation session, persisted to ConfigDB."""

    def __init__(self, session_id: str, title: str = ""):
        self.session_id = session_id
        self.created_at = time.time()
        self.last_active = time.time()
        self.messages: list[dict] = []
        self.summary: str = ""
        self.metadata: dict[str, Any] = {"title": title}
        self._title = title or ""
        logger.debug(f"Session created: {session_id}")

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str):
        old = self._title
        self._title = value
        self.metadata["title"] = value
        try:
            with scoped_session() as session:
                session.query(SessionModel).filter_by(id=self.session_id).update({
                    "title": value,
                    "updated_at": time.time(),
                })
        except Exception:
            pass
        logger.info(f"Session {self.session_id}: rename '{old}' -> '{value}'")

    def add_message(self, role: str, content: str, tool_calls: list = None) -> None:
        self.last_active = time.time()
        msg = {"role": role, "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)
        logger.debug(f"Session {self.session_id}: +{role} msg ({len(content)} chars)")
        self._maybe_compress()

        # Persist to ConfigDB
        try:
            with scoped_session() as session:
                existing = session.query(SessionModel).filter_by(id=self.session_id).first()
                if not existing:
                    session.add(SessionModel(
                        id=self.session_id,
                        title=self._title,
                        created_at=self.created_at,
                        updated_at=self.last_active,
                    ))
                session.add(Message(
                    session_id=self.session_id,
                    role=role,
                    content=content,
                    created_at=time.time(),
                ))
        except Exception:
            pass

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
    """Manages all active sessions, backed by ConfigDB."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._timeout: int = 3600  # 1 hour

        # Load existing sessions from ConfigDB
        try:
            with scoped_session() as session:
                rows = session.query(SessionModel).order_by(SessionModel.updated_at.desc()).all()
                logger.info(f"Loading {len(rows)} sessions from ConfigDB...")
                for m in rows:
                    sess = Session(m.id, m.title or "")
                    sess.created_at = m.created_at
                    sess.last_active = m.updated_at
                    # Load messages
                    msgs = session.query(Message).filter_by(session_id=m.id).order_by(Message.id).all()
                    for msg in msgs:
                        sess.messages.append({"role": msg.role, "content": msg.content})
                    # Auto-title from first user message
                    for msg in sess.messages:
                        if msg["role"] == "user" and not m.title:
                            sess.title = msg["content"][:30] + ("…" if len(msg["content"]) > 30 else "")
                            break
                    self._sessions[m.id] = sess
                logger.info(f"Loaded {len(self._sessions)} sessions ({sum(len(s.messages) for s in self._sessions.values())} messages)")
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")

    def get_or_create(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id)
        return self._sessions[session_id]

    def delete(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]
        try:
            with scoped_session() as session:
                session.query(Message).filter_by(session_id=session_id).delete()
                session.query(SessionModel).filter_by(id=session_id).delete()
        except Exception:
            pass

    def rename(self, session_id: str, title: str) -> None:
        sess = self._sessions.get(session_id)
        if sess:
            sess.title = title

    def clear_all(self) -> int:
        """Delete ALL sessions from memory and ConfigDB. Returns count of deleted sessions."""
        count = len(self._sessions)
        self._sessions.clear()
        try:
            with scoped_session() as session:
                session.query(Message).delete()
                session.query(SessionModel).delete()
        except Exception:
            pass
        logger.info(f"Cleared all {count} sessions")
        return count

    def cleanup_expired(self) -> None:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_active > self._timeout
        ]
        for sid in expired:
            self.delete(sid)
