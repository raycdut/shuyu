from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .. import state

logger = logging.getLogger("shuyu.main")

DEFAULT_SYSTEM_CONFIG: dict[str, Any] = {
    "llm": {
        "provider_pool": [
            {"provider": "openai", "label": "OpenAI", "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"], "enabled": True},
            {"provider": "deepseek", "label": "DeepSeek", "models": ["deepseek-v4-flash", "deepseek-v4-pro"], "enabled": True},
            {"provider": "azure", "label": "Azure OpenAI", "models": ["gpt-4o", "gpt-4", "gpt-35-turbo"], "enabled": False},
            {"provider": "anthropic", "label": "Anthropic", "models": ["claude-3-5-sonnet", "claude-3-haiku"], "enabled": False},
            {"provider": "ollama", "label": "Ollama", "models": ["llama3.1", "qwen2.5", "mistral"], "enabled": True},
        ],
        "default_model": "gpt-4o",
    },
    "safety": {
        "read_only": True,
        "require_approval": True,
        "max_rows": 1000,
        "blocked_tables": [],
        "masked_columns": [],
    },
    "advanced": {
        "session_expire_minutes": 1440,
        "max_sessions_per_user": 50,
        "allow_user_llm_config": True,
        "allow_user_safety_override": False,
        "llm_temperature_range": {"min": 0, "max": 1, "default": 0.3},
    },
    "storage": {
        "log_interval": "day",
        "log_retention_days": 30,
    },
}

DEFAULT_USER_CONFIG: dict[str, Any] = {
    "llm": {},
    "safety": {},
    "preferences": {
        "language": "zh-CN",
        "temperature": 0.3,
        "theme": "light",
        "default_view": "chat",
    },
}


def _get_db():
    if state._sqlite is None:
        raise RuntimeError("Database not initialized")
    return state._sqlite


def get_system_config() -> dict[str, Any]:
    db = _get_db()
    row = db.execute("SELECT config FROM system_config WHERE id = 1").fetchone()
    if not row:
        return dict(DEFAULT_SYSTEM_CONFIG)
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return dict(DEFAULT_SYSTEM_CONFIG)


def update_system_config(config: dict[str, Any], updated_by: str | None = None) -> dict[str, Any]:
    db = _get_db()
    old = get_system_config()
    merged = {**old, **config}
    for key in ("llm", "safety", "advanced", "storage"):
        if key in config and isinstance(config[key], dict):
            merged[key] = {**old.get(key, {}), **config[key]}
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO system_config (id, config, updated_at, updated_by) VALUES (1, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET config = ?, updated_at = ?, updated_by = ?",
        (json.dumps(merged), now, updated_by, json.dumps(merged), now, updated_by),
    )
    db.commit()
    _log_config_change("system", None, updated_by or "unknown", f"更新系统配置: {list(config.keys())}")
    return get_system_config()


def get_user_config(user_id: str) -> dict[str, Any]:
    db = _get_db()
    row = db.execute("SELECT config FROM user_configs WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return dict(DEFAULT_USER_CONFIG)
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return dict(DEFAULT_USER_CONFIG)


def update_user_config(user_id: str, config: dict[str, Any]) -> dict[str, Any]:
    db = _get_db()
    old = get_user_config(user_id)
    merged = {**old}
    for key in ("llm", "safety", "preferences"):
        if key in config and isinstance(config[key], dict):
            merged[key] = {**old.get(key, {}), **config[key]}
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO user_configs (user_id, config, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET config = ?, updated_at = ?",
        (user_id, json.dumps(merged), now, json.dumps(merged), now),
    )
    db.commit()
    _log_config_change("user", user_id, user_id, f"更新个人配置: {list(config.keys())}")
    overrides = {k: config[k] for k in config if k in merged}
    return {"merged": get_merged_config(user_id), "overrides": overrides}


def get_merged_config(user_id: str | None = None) -> dict[str, Any]:
    system = get_system_config()
    if user_id is None:
        return _system_to_runtime(system)
    user = get_user_config(user_id)
    return _merge_configs(system, user)


def _system_to_runtime(system: dict[str, Any]) -> dict[str, Any]:
    pool = system.get("llm", {}).get("provider_pool", [])
    enabled = [p for p in pool if p.get("enabled")]
    first_provider = enabled[0]["provider"] if enabled else "openai"
    first_model = enabled[0]["models"][0] if enabled and enabled[0].get("models") else "gpt-4o"
    return {
        "llm": {
            "provider": first_provider,
            "model": system.get("llm", {}).get("default_model", first_model),
            "api_key": state.config.llm.api_key if state.config.llm.api_key else "",
            "api_base": state.config.llm.api_base or "",
            "timeout": state.config.llm.timeout,
        },
        "safety": {
            "read_only": system.get("safety", {}).get("read_only", True),
            "require_approval": system.get("safety", {}).get("require_approval", True),
            "max_rows": system.get("safety", {}).get("max_rows", 1000),
        },
    }


def _merge_configs(system: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    runtime = _system_to_runtime(system)
    advanced = system.get("advanced", {})
    user_llm = user.get("llm", {})
    user_safety = user.get("safety", {})
    user_prefs = user.get("preferences", {})

    if advanced.get("allow_user_llm_config") and user_llm.get("provider"):
        runtime["llm"]["provider"] = user_llm["provider"]
    if advanced.get("allow_user_llm_config") and user_llm.get("model"):
        runtime["llm"]["model"] = user_llm["model"]
    if user_llm.get("api_key"):
        runtime["llm"]["api_key"] = user_llm["api_key"]

    if advanced.get("allow_user_safety_override"):
        if "read_only" in user_safety:
            runtime["safety"]["read_only"] = user_safety["read_only"]
        if "require_approval" in user_safety:
            runtime["safety"]["require_approval"] = user_safety["require_approval"]
        if "max_rows" in user_safety:
            max_allowed = system.get("safety", {}).get("max_rows", 10000)
            runtime["safety"]["max_rows"] = min(user_safety["max_rows"], max_allowed)

    preferences = {
        "language": user_prefs.get("language", "zh-CN"),
        "temperature": user_prefs.get("temperature", 0.3),
        "theme": user_prefs.get("theme", "light"),
        "default_view": user_prefs.get("default_view", "chat"),
    }
    runtime["preferences"] = preferences
    return runtime


def get_user_available_options(user_id: str) -> dict[str, Any]:
    system = get_system_config()
    advanced = system.get("advanced", {})
    pool = system.get("llm", {}).get("provider_pool", [])
    enabled_providers = [
        {"provider": p["provider"], "label": p.get("label", p["provider"]), "models": p.get("models", [])}
        for p in pool if p.get("enabled")
    ]
    temp_range = advanced.get("llm_temperature_range", {"min": 0, "max": 1, "default": 0.3})
    return {
        "llm": {
            "providers": enabled_providers,
            "can_use_custom_api_key": True,
            "can_use_custom_api_base": True,
        },
        "safety": {
            "read_only": {"editable": advanced.get("allow_user_safety_override", False), "value": system.get("safety", {}).get("read_only", True)},
            "require_approval": {"editable": advanced.get("allow_user_safety_override", False), "value": system.get("safety", {}).get("require_approval", True)},
            "max_rows": {"editable": advanced.get("allow_user_safety_override", False), "min": 10, "max": system.get("safety", {}).get("max_rows", 10000), "default": 1000},
        },
        "preferences": {
            "language": {"options": ["zh-CN", "en", "ja"]},
            "temperature": {"min": temp_range.get("min", 0), "max": temp_range.get("max", 1), "step": 0.1},
        },
    }


def get_config_changelog(config_type: str | None = None, limit: int = 50) -> list[dict]:
    db = _get_db()
    if config_type:
        rows = db.execute(
            "SELECT id, config_type, user_id, changed_by, summary, diff, created_at FROM config_changelog WHERE config_type = ? ORDER BY created_at DESC LIMIT ?",
            (config_type, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, config_type, user_id, changed_by, summary, diff, created_at FROM config_changelog ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {"id": r[0], "config_type": r[1], "user_id": r[2], "changed_by": r[3], "summary": r[4], "diff": r[5], "created_at": r[6]}
        for r in rows
    ]


def _log_config_change(config_type: str, user_id: str | None, changed_by: str, summary: str, diff: str | None = None):
    db = _get_db()
    db.execute(
        "INSERT INTO config_changelog (config_type, user_id, changed_by, summary, diff, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (config_type, user_id, changed_by, summary, diff, datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
