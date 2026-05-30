"""Configuration — defaults only, persisted via SQLite."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# Project root = backend/app/config.py -> backend/ -> ../
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    api_base: Optional[str] = None
    timeout: int = 120


class SafetyConfig(BaseModel):
    read_only: bool = True
    restricted_tables: list[str] = Field(default_factory=list)
    masked_columns: list[str] = Field(default_factory=list)
    max_rows: int = 1000


class StorageConfig(BaseModel):
    path: str = str(_PROJECT_ROOT / "backend" / "data" / "config.db")


class Config(BaseModel):
    llm: LLMConfig = LLMConfig()
    safety: SafetyConfig = SafetyConfig()
    storage: StorageConfig = StorageConfig()


def load_config() -> Config:
    """Create config from defaults + environment variable overrides."""
    raw: dict = {}

    env_map = {
        ("llm", "api_key"): "LLM_API_KEY",
        ("llm", "provider"): "LLM_PROVIDER",
        ("llm", "model"): "LLM_MODEL",
        ("llm", "api_base"): "LLM_API_BASE",
    }

    for (section, field), env_key in env_map.items():
        value = os.environ.get(env_key)
        if value is not None:
            if section not in raw:
                raw[section] = {}
            raw[section][field] = value

    return Config(**raw)
