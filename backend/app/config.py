"""Configuration — default values only, no YAML. Persisted via DuckDB."""

from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    api_base: Optional[str] = None


class DatabaseConfig(BaseModel):
    type: str = "duckdb"
    path: str = "./data/analytics.db"
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    include_tables: Optional[list[str]] = None
    exclude_tables: Optional[list[str]] = None


class KnowledgeBaseConfig(BaseModel):
    type: str = "chromadb"
    path: str = "./data/kb/"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class StorageConfig(BaseModel):
    path: str = "./data/sessions.db"


class SafetyConfig(BaseModel):
    read_only: bool = True
    restricted_tables: list[str] = Field(default_factory=list)
    masked_columns: list[str] = Field(default_factory=list)
    max_rows: int = 1000


class PrivacyConfig(BaseModel):
    require_approval_for: list[str] = Field(default_factory=lambda: ["query_results"])
    audit_log: bool = True


class Config(BaseModel):
    llm: LLMConfig = LLMConfig()
    database: DatabaseConfig = DatabaseConfig()
    knowledge_base: KnowledgeBaseConfig = KnowledgeBaseConfig()
    server: ServerConfig = ServerConfig()
    storage: StorageConfig = StorageConfig()
    safety: SafetyConfig = SafetyConfig()
    privacy: PrivacyConfig = PrivacyConfig()


def load_config() -> Config:
    """Create config from defaults + environment variable overrides (no YAML)."""
    raw: dict = {}

    # Resolve env var overrides
    env_map = {
        ("llm", "api_key"): "LLM_API_KEY",
        ("llm", "provider"): "LLM_PROVIDER",
        ("llm", "model"): "LLM_MODEL",
        ("llm", "api_base"): "LLM_API_BASE",
        ("database", "type"): "DB_TYPE",
        ("database", "path"): "DB_PATH",
        ("database", "host"): "DB_HOST",
        ("database", "port"): "DB_PORT",
        ("database", "user"): "DB_USER",
        ("database", "password"): "DB_PASSWORD",
        ("database", "database"): "DB_NAME",
        ("server", "port"): "PORT",
    }

    for (section, field), env_key in env_map.items():
        value = os.environ.get(env_key)
        if value is not None:
            if section not in raw:
                raw[section] = {}
            raw[section][field] = value

    return Config(**raw)
