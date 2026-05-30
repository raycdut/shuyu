"""Configuration — defaults + YAML file + env var overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# Project root = backend/app/config.py -> backend/ -> ../
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_FILE = PROJECT_ROOT / "backend" / "config.yaml"


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
    path: str = str(PROJECT_ROOT / "backend" / "data" / "config.db")
    log_interval: str = "day"
    log_retention_days: int = 30


class Config(BaseModel):
    llm: LLMConfig = LLMConfig()
    safety: SafetyConfig = SafetyConfig()
    storage: StorageConfig = StorageConfig()


def load_config() -> Config:
    """Load config: 1) Python defaults → 2) config.yaml → 3) env overrides."""
    raw: dict = {}

    # --- Phase 1: Load from YAML file ---
    yaml_path = _CONFIG_FILE
    if yaml_path.exists():
        try:
            import yaml
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
                for section, values in data.items():
                    if isinstance(values, dict):
                        raw.setdefault(section, {}).update(values)
        except Exception as e:
            import logging
            logging.getLogger("shuyu.main").warning(f"Failed to load config.yaml: {e}")

    # --- Phase 2: Environment overrides ---
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
