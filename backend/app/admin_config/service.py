"""Admin config service — system and user configuration management via SQLAlchemy ORM."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .. import state
from ..configdb.base import scoped_session
from ..configdb.models.config import SystemConfig, UserConfig, ConfigChangelog
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
                "provider": "openai",
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
    "rag": {
        "enabled": False,
        "provider": "openai",
        "model": "text-embedding-3-small",
        "api_key": "",
        "api_base": "",
        "top_k": 5,
        "min_score": 0.3,
        "self_learn": False,
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


def get_system_config() -> dict[str, Any]:
    try:
        with scoped_session() as session:
            row = session.query(SystemConfig).filter_by(id=1).first()
            if not row:
                return dict(DEFAULT_SYSTEM_CONFIG)
            config = json.loads(row.config) if row.config else {}
            if not config:
                return dict(DEFAULT_SYSTEM_CONFIG)
            models = config.get("llm", {}).get("models", [])
            for m in models:
                if m.get("api_key"):
                    m["api_key"] = decrypt_value(m["api_key"]) or ""
            rag_api_key = config.get("rag", {}).get("api_key", "")
            if rag_api_key:
                config["rag"] = {**config.get("rag", {}), "api_key": decrypt_value(rag_api_key) or ""}
            return config
    except (json.JSONDecodeError, TypeError, Exception):
        return dict(DEFAULT_SYSTEM_CONFIG)


def _mask_api_key(key: str) -> str:
    if not key or len(key) < 8:
        return ""
    return key[:4] + "••••" + key[-4:]


def _unmask_and_merge_api_keys(old_models: list[dict], new_models: list[dict]) -> list[dict]:
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
    old = get_system_config()
    merged = {**old}

    for key in ("safety", "advanced", "storage"):
        if key in config and isinstance(config[key], dict):
            merged[key] = {**old.get(key, {}), **config[key]}

    if "llm" in config:
        merged_llm = {**old.get("llm", {})}
        if "models" in config["llm"]:
            old_models = old.get("llm", {}).get("models", [])
            incoming = config["llm"]["models"]
            incoming = _unmask_and_merge_api_keys(old_models, incoming)
            incoming = _ensure_default_model(incoming)
            for m in incoming:
                if m.get("api_key"):
                    m["api_key"] = encrypt_value(m["api_key"]) or ""
            merged_llm["models"] = incoming
        merged["llm"] = merged_llm

    if "rag" in config and isinstance(config["rag"], dict):
        old_rag = old.get("rag", {})
        incoming_rag = {**old_rag, **config["rag"]}
        if incoming_rag.get("api_key") and "••••" not in incoming_rag["api_key"]:
            incoming_rag["api_key"] = encrypt_value(incoming_rag["api_key"]) or ""
        elif "••••" in incoming_rag.get("api_key", ""):
            incoming_rag["api_key"] = old_rag.get("api_key", "")
        merged["rag"] = incoming_rag

    now = datetime.now(timezone.utc).isoformat()
    with scoped_session() as session:
        row = session.query(SystemConfig).filter_by(id=1).first()
        if row:
            row.config = json.dumps(merged)
            row.updated_at = now
            row.updated_by = updated_by
        else:
            session.add(SystemConfig(id=1, config=json.dumps(merged), updated_at=now, updated_by=updated_by))

    _log_config_change("system", None, updated_by or "unknown", f"更新系统配置: {list(config.keys())}")

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
    config = get_system_config()
    models = config.get("llm", {}).get("models", [])
    for m in models:
        if m.get("api_key"):
            m["api_key"] = _mask_api_key(m["api_key"])
    rag_api_key = config.get("rag", {}).get("api_key", "")
    if rag_api_key:
        config["rag"] = {**config.get("rag", {}), "api_key": _mask_api_key(rag_api_key)}
    return config


def get_user_config(user_id: str) -> dict[str, Any]:
    try:
        with scoped_session() as session:
            row = session.query(UserConfig).filter_by(user_id=user_id).first()
            if not row:
                return dict(DEFAULT_USER_CONFIG)
            return json.loads(row.config) if row.config else dict(DEFAULT_USER_CONFIG)
    except (json.JSONDecodeError, TypeError, Exception):
        return dict(DEFAULT_USER_CONFIG)


def update_user_config(user_id: str, config: dict[str, Any]) -> dict[str, Any]:
    old = get_user_config(user_id)
    merged = {**old}
    for key in ("llm", "safety", "preferences"):
        if key in config and isinstance(config[key], dict):
            merged[key] = {**old.get(key, {}), **config[key]}
    if "preferences" in merged and "temperature" in merged["preferences"]:
        temp_range = get_system_config().get("advanced", {}).get("llm_temperature_range", {"min": 0, "max": 0.5, "default": 0.3})
        merged["preferences"]["temperature"] = max(temp_range.get("min", 0), min(merged["preferences"]["temperature"], temp_range.get("max", 0.5)))
    now = datetime.now(timezone.utc).isoformat()
    with scoped_session() as session:
        row = session.query(UserConfig).filter_by(user_id=user_id).first()
        if row:
            row.config = json.dumps(merged)
            row.updated_at = now
        else:
            session.add(UserConfig(user_id=user_id, config=json.dumps(merged), updated_at=now))
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
    default_model = next((m for m in models if m.get("is_system_default")), None)
    if not default_model:
        default_model = next((m for m in models if m.get("enabled")), None)
    if not default_model:
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
    try:
        with scoped_session() as session:
            q = session.query(ConfigChangelog)
            if config_type:
                q = q.filter_by(config_type=config_type)
            rows = q.order_by(ConfigChangelog.created_at.desc()).limit(limit).all()
            return [
                {"id": r.id, "config_type": r.config_type, "user_id": r.user_id,
                 "changed_by": r.changed_by, "summary": r.summary, "diff": r.diff,
                 "created_at": r.created_at.isoformat() if hasattr(r.created_at, 'isoformat') else str(r.created_at)}
                for r in rows
            ]
    except Exception:
        return []


def _log_config_change(config_type: str, user_id: str | None, changed_by: str, summary: str, diff: str | None = None):
    try:
        with scoped_session() as session:
            session.add(ConfigChangelog(
                config_type=config_type,
                user_id=user_id,
                changed_by=changed_by,
                summary=summary,
                diff=diff,
                created_at=datetime.now(timezone.utc).isoformat(),
            ))
    except Exception:
        pass


def log_user_management_change(changed_by: str, summary: str, target_user_id: str | None = None, diff: str | None = None):
    _log_config_change("user_mgmt", target_user_id, changed_by, summary, diff)


def log_database_change(changed_by: str, summary: str, diff: str | None = None):
    _log_config_change("database", None, changed_by, summary, diff)
