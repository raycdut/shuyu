"""Tests for session/manager.py — Session compression, add_message."""

from __future__ import annotations

import pytest

from app.session.manager import Session, SessionManager


class TestSession:
    def test_create(self):
        s = Session("test-1")
        assert s.session_id == "test-1"
        assert len(s.messages) == 0
        assert s.summary == ""

    def test_add_message(self):
        s = Session("test-1")
        s.add_message("user", "你好")
        assert len(s.messages) == 1
        assert s.messages[0]["role"] == "user"
        assert s.messages[0]["content"] == "你好"

    def test_get_messages_empty(self):
        s = Session("test-1")
        msgs = s.get_messages()
        assert msgs == []

    def test_get_messages_with_summary(self):
        s = Session("test-1")
        s.summary = "之前聊过天气"
        s.add_message("user", "今天呢？")
        msgs = s.get_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert "对话摘要" in msgs[0]["content"]

    def test_compression_triggers(self):
        """Sliding window: MAX_MESSAGES=20, keep KEEP_RECENT=6 most recent pairs."""
        s = Session("test-1")
        # Add 21 user/assistant pairs (42 messages total)
        for i in range(21):
            s.add_message("user", f"msg{i}")
            s.add_message("assistant", f"ans{i}")

        # Should have compressed — summary exists, only recent kept
        assert s.summary != ""
        assert len(s.messages) <= 16  # KEEP_RECENT * 2 + tool results

    def test_compression_not_needed(self):
        """Under MAX_MESSAGES, no compression."""
        s = Session("test-1")
        for i in range(10):
            s.add_message("user", f"msg{i}")
            s.add_message("assistant", f"ans{i}")
        assert s.summary == ""

    def test_add_tool_result(self):
        s = Session("test-1")
        s.add_tool_result("call-1", '{"result": "ok"}')
        assert s.messages[0]["role"] == "tool"
        assert s.messages[0]["tool_call_id"] == "call-1"

    def test_metadata(self):
        s = Session("test-1")
        assert "title" in s.metadata  # already initialized
        s.metadata["title"] = "测试会话"
        assert s.metadata["title"] == "测试会话"


class TestSessionManager:
    def test_get_or_create(self):
        mgr = SessionManager()
        s1 = mgr.get_or_create("s1")
        s2 = mgr.get_or_create("s1")
        assert s1 is s2  # same object

    def test_get_or_create_new(self):
        mgr = SessionManager()
        s1 = mgr.get_or_create("a")
        s2 = mgr.get_or_create("b")
        assert s1 is not s2

    def test_delete(self):
        mgr = SessionManager()
        mgr.get_or_create("x")
        assert "x" in mgr._sessions
        mgr.delete("x")
        assert "x" not in mgr._sessions

    def test_rename(self):
        mgr = SessionManager()
        s = mgr.get_or_create("s1")
        s.metadata["title"] = "旧标题"
        mgr.rename("s1", "新标题")
        assert s.metadata.get("title") == "新标题"

    def test_cleanup_expired(self):
        import time
        mgr = SessionManager()
        mgr._timeout = 0  # expire immediately
        s = mgr.get_or_create("expired")
        s.last_active = time.time() - 100  # old timestamp
        mgr.cleanup_expired()
        assert "expired" not in mgr._sessions
