from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ConfigUpdate(BaseModel):
    llm: dict[str, Any] | None = None
    safety: dict[str, Any] | None = None


class LLMTestResult(BaseModel):
    ok: bool
    message: str
