"""Pydantic schemas for API request/response."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    db_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tool_calls: list[dict] = []


class SchemaInfo(BaseModel):
    tables: list[dict]


class PrivacyLogEntry(BaseModel):
    timestamp: str
    user_approved: bool
    session_id: str
    llm_call_type: str
    sent_to_llm: dict
    approval_required: bool


# ---- Phase 1.2 — Config & database management ----


class DBConnectRequest(BaseModel):
    name: str = ""
    type: str = "duckdb"
    path: str | None = None
    connection_string: str | None = None
    host: str | None = None
    port: int | None = None
    user: str | None = None
    password: str | None = None
    database: str | None = None
    include_tables: list[str] | None = None
    exclude_tables: list[str] | None = None


class DBInfo(BaseModel):
    id: str
    name: str
    type: str
    connection_string: str | None = None
    include_tables: list[str] | None = None
    exclude_tables: list[str] | None = None
    is_active: bool = False


class DBTestResult(BaseModel):
    ok: bool
    message: str


class ConfigUpdate(BaseModel):
    llm: dict[str, Any] | None = None
    safety: dict[str, Any] | None = None


class LLMTestResult(BaseModel):
    ok: bool
    message: str


class SessionRenameRequest(BaseModel):
    title: str


class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: list[dict]
