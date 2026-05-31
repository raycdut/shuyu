from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .. import state
from ..utils.crypto import decrypt_value, encrypt_value

logger = logging.getLogger("shuyu.main")

DEFAULT_SYSTEM_CONFIG: dict[str, Any] = {
    "llm": {
        "models": [
            {
                "id": "default-openai",
                "name": "OpenAI (Default)",
                "provider": "openai",
                "model": "gpt-4o",
                "api_key": "",
                "api_base": "https://api.openai.com/v1",
                "timeout": 120,
                "enabled": True,
                "is_system_default": True
            },
            {
                "id": "default-deepseek",
                "name": "DeepSeek",
                "provider": "openai",  # DeepSeek uses OpenAI compatible API
                "model": "deepseek-chat",
                "api_key": "",
                "api_base": "https://api.deepseek.com/v1",
                "timeout": 120,
                "enabled": True,
                "is_system_default": False
            }
        ],
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
        "llm_temperature_range": {"min": 0, "max": 0.5, "default": 0.3},
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
        config = json.loads(row[0])
        # Decrypt API keys transparently
        models = config.get("llm", {}).get("models", [])
        for m in models:
            if m.get("api_key"):
                m["api_key"] = decrypt_value(m["api_key"]) or ""
        return config
    except (json.JSONDecodeError, TypeError):
        return dict(DEFAULT_SYSTEM_CONFIG)


def _mask_api_key(key: str) -> str:
    """Mask API key for safe display (show first 4 + last 4 chars if long enough)."""
    if not key or len(key) < 8:
        return ""
    return key[:4] + "••••" + key[-4:]


def _unmask_and_merge_api_keys(old_models: list[dict], new_models: list[dict]) -> list[dict]:
    """Merge API keys from old models if new ones are masked placeholders."""
    old_map = {m["id"]: m.get("api_key", "") for m in old_models if m.get("id")}
    result = []
    for m in new_models:
        mid = m.get("id", "")
        key = m.get("api_key", "")
        if key and "••••" in key and mid in old_map:
            key = old_map[mid]
        result.append({**m, "api_key": key})
    return result


def _ensure_default_model(models: list[dict]) -> list[dict]:
    """Ensure exactly one model has is_system_default=True."""
    defaults = [m for m in models if m.get("is_system_default")]
    if len(defaults) > 1:
        for m in defaults[1:]:
            m["is_system_default"] = False
    if not defaults:
        enabled = [m for m in models if m.get("enabled")]
        if enabled:
            enabled[0]["is_system_default"] = True
    return models


def update_system_config(config: dict[str, Any], updated_by: str | None = None) -> dict[str, Any]:
    db = _get_db()
    old = get_system_config()
    merged = {**old}

    for key in ("safety", "advanced", "storage"):
        if key in config and isinstance(config[key], dict):
            merged[key] = {**old.get(key, {}), **config[key]}

    # Handle models list specially (full replacement, not dict merge)
    if "llm" in config:
        merged_llm = {**old.get("llm", {})}
        if "models" in config["llm"]:
            old_models = old.get("llm", {}).get("models", [])
            incoming = config["llm"]["models"]
            # Preserve real API keys if masked values were sent
            incoming = _unmask_and_merge_api_keys(old_models, incoming)
            # Ensure exactly one model is system default
            incoming = _ensure_default_model(incoming)
            # Encrypt API keys before storing
            for m in incoming:
                if m.get("api_key"):
                    m["api_key"] = encrypt_value(m["api_key"]) or ""
            merged_llm["models"] = incoming
        merged["llm"] = merged_llm

    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO system_config (id, config, updated_at, updated_by) VALUES (1, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET config = ?, updated_at = ?, updated_by = ?",
        (json.dumps(merged), now, updated_by, json.dumps(merged), now, updated_by),
    )
    db.commit()
    _log_config_change("system", None, updated_by or "unknown", f"更新系统配置: {list(config.keys())}")

    # Sync the default model's API key into runtime config so call_llm() picks it up immediately
    result = get_system_config()
    models = result.get("llm", {}).get("models", [])
    default_model = next((m for m in models if m.get("is_system_default")), models[0] if models else None)
    if default_model and default_model.get("api_key"):
        import os as _os
        if not _os.environ.get("LLM_API_KEY"):
            state.config.llm.api_key = default_model["api_key"]
            state.config.llm.model = default_model.get("model", state.config.llm.model)
            if default_model.get("api_base"):
                state.config.llm.api_base = default_model["api_base"]
            if default_model.get("provider"):
                state.config.llm.provider = default_model["provider"]
            logger.info("Runtime API key synced from admin system_config")

    return result


def get_system_config_masked() -> dict[str, Any]:
    """Return system config with API keys masked for frontend display."""
    config = get_system_config()
    models = config.get("llm", {}).get("models", [])
    for m in models:
        if m.get("api_key"):
            m["api_key"] = _mask_api_key(m["api_key"])
    return config


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
    if "preferences" in merged and "temperature" in merged["preferences"]:
        temp_range = get_system_config().get("advanced", {}).get("llm_temperature_range", {"min": 0, "max": 0.5, "default": 0.3})
        merged["preferences"]["temperature"] = max(temp_range.get("min", 0), min(merged["preferences"]["temperature"], temp_range.get("max", 0.5)))
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
    models = system.get("llm", {}).get("models", [])
    # Find system default model, or first enabled one
    default_model = next((m for m in models if m.get("is_system_default")), None)
    if not default_model:
        default_model = next((m for m in models if m.get("enabled")), None)
    
    if not default_model:
        # Fallback to something safe
        return {
            "llm": {
                "id": "fallback",
                "provider": "openai",
                "model": "gpt-4o",
                "api_key": "",
                "api_base": "",
                "timeout": 120,
            },
            "safety": {
                "read_only": system.get("safety", {}).get("read_only", True),
                "require_approval": system.get("safety", {}).get("require_approval", True),
                "max_rows": system.get("safety", {}).get("max_rows", 1000),
            },
        }

    return {
        "llm": {
            "id": default_model.get("id"),
            "name": default_model.get("name"),
            "provider": default_model.get("provider", "openai"),
            "model": default_model.get("model", "gpt-4o"),
            "api_key": default_model.get("api_key") or state.config.llm.api_key or "",
            "api_base": default_model.get("api_base") or state.config.llm.api_base or "",
            "timeout": default_model.get("timeout", 120),
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

    # If user has a default model selected
    user_default_id = user_llm.get("default_model_id")
    if user_default_id:
        models = system.get("llm", {}).get("models", [])
        target = next((m for m in models if m.get("id") == user_default_id), None)
        if target and target.get("enabled"):
            runtime["llm"] = {
                "id": target.get("id"),
                "name": target.get("name"),
                "provider": target.get("provider", "openai"),
                "model": target.get("model", "gpt-4o"),
                "api_key": target.get("api_key") or state.config.llm.api_key or "",
                "api_base": target.get("api_base") or state.config.llm.api_base or "",
                "timeout": target.get("timeout", 120),
            }

    # Allow user to override API Key if needed (legacy or specific use cases)
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

    temp_range = advanced.get("llm_temperature_range", {"min": 0, "max": 0.5, "default": 0.3})
    user_temp = user_prefs.get("temperature", 0.3)
    clamped_temp = max(temp_range.get("min", 0), min(user_temp, temp_range.get("max", 0.5)))
    preferences = {
        "language": user_prefs.get("language", "zh-CN"),
        "temperature": clamped_temp,
        "theme": user_prefs.get("theme", "light"),
        "default_view": user_prefs.get("default_view", "chat"),
    }
    runtime["preferences"] = preferences
    return runtime


def get_user_available_options(user_id: str) -> dict[str, Any]:
    system = get_system_config()
    advanced = system.get("advanced", {})
    models = system.get("llm", {}).get("models", [])
    enabled_models = [
        {
            "id": m.get("id"),
            "name": m.get("name", ""),
            "provider": m.get("provider", ""),
            "model": m.get("model", ""),
        }
        for m in models if m.get("enabled")
    ]
    # Group by provider for backwards compatibility
    from collections import OrderedDict
    provider_groups: dict[str, dict] = OrderedDict()
    for m in enabled_models:
        provider = m["provider"]
        if provider not in provider_groups:
            provider_groups[provider] = {"provider": provider, "label": provider.capitalize(), "models": []}
        provider_groups[provider]["models"].append(m["model"])
    enabled_providers = list(provider_groups.values())

    temp_range = advanced.get("llm_temperature_range", {"min": 0, "max": 0.5, "default": 0.3})
    return {
        "llm": {
            "providers": enabled_providers,
            "models": enabled_models,
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


def log_user_management_change(changed_by: str, summary: str, target_user_id: str | None = None, diff: str | None = None):
    """Record a user management operation (create / update / delete user) into config_changelog."""
    _log_config_change("user_mgmt", target_user_id, changed_by, summary, diff)


def log_database_change(changed_by: str, summary: str, diff: str | None = None):
    """Record a database management operation (connect / update / delete / schema) into config_changelog."""
    _log_config_change("database", None, changed_by, summary, diff)
