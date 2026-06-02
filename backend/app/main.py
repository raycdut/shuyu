"""Agentic Data Analyst — FastAPI server entry point (slim).

App assembly: lifespan → load config/persistence → register tools → mount routes.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import state
from .agent.advanced_agent import AdvancedAgent
from .agent.simple_agent import SimpleAgent
from .agent.tools.registry import Tool, ToolRegistry
from .config import load_config
from .configdb import init_configdb, _get_default_prompt_content
from .persistence.config import load_config_sqlite
from .persistence.database import load_db_connections_sqlite
from .client import call_llm
from .agent.tools.sql_tool import handle_query_database
from .routes import admin_stats, chat, config as config_route, database, schema, sessions
from .auth.router import router as auth_router
from .auth.service import init_auth_config
from .admin_config.router import router as admin_config_router
from .session.manager import SessionManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("shuyu.main")
for name in ("shuyu.main", "shuyu.session", "shuyu.agent", "shuyu.registry", "shuyu.db"):
    l = logging.getLogger(name)
    l.setLevel(logging.INFO)
    l.propagate = True

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


def _setup_logging():
    """Configure file + stderr logging (after uvicorn starts).

    Log file rotates based on storage.log_interval config:
    - "hour" → one file per hour (shuyu.YYYY-MM-DD_HH.log)
    - "day"  → one file per day  (shuyu.YYYY-MM-DD.log)
    """
    import logging as _logging
    from logging.handlers import TimedRotatingFileHandler

    from .config import PROJECT_ROOT

    root = _logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(_logging.INFO)
    fmt = _logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")

    log_dir = PROJECT_ROOT / "backend" / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = str(log_dir / "shuyu.log")

    interval = state.config.storage.log_interval
    when = "H" if interval == "hour" else "MIDNIGHT"
    suffix = "%Y-%m-%d_%H" if interval == "hour" else "%Y-%m-%d"
    retention = state.config.storage.log_retention_days

    fh = TimedRotatingFileHandler(
        log_path,
        when=when,
        interval=1,
        backupCount=retention,
    )
    fh.suffix = suffix
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = _logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config, connector, tool_registry, agent_loop, session_manager, schema_prompt

    # 0. Load config first (logging setup needs it)
    state.config = load_config()
    _setup_logging()
    logger.info(f"Config loaded: LLM={state.config.llm.provider}/{state.config.llm.model}")

    # 1.1 Init auth config (JWT secret etc.)
    init_auth_config()

    # 2. Init ConfigDB (SQLite or MySQL via SQLAlchemy)
    configdb_url = os.environ.get("CONFIGDB_URL", "").strip() or None
    init_configdb(configdb_url)
    load_config_sqlite()
    load_db_connections_sqlite()
    logger.info(f"ConfigDB ready: {len(state._db_connections)} DB connections loaded")

    # Sync API key from admin system_config (encrypted path) into runtime config
    # so call_llm() can use it without requiring a separate POST /api/config call.
    try:
        from app.admin_config.service import get_system_config
        sys_cfg = get_system_config()
        models = sys_cfg.get("llm", {}).get("models", [])
        if models:
            default = next((m for m in models if m.get("is_system_default")), models[0])
            if default.get("api_key") and not os.environ.get("LLM_API_KEY"):
                state.config.llm.api_key = default["api_key"]
                state.config.llm.model = default.get("model", state.config.llm.model)
                if default.get("api_base"):
                    state.config.llm.api_base = default["api_base"]
                if default.get("provider"):
                    state.config.llm.provider = default["provider"]
                logger.info(f"API key synced from system_config: {default.get('model', 'unknown')}")
    except Exception as e:
        logger.warning(f"Failed to sync API key from system_config: {e}")

    # 2.5 Init RAG if enabled
    try:
        from app.admin_config.service import get_system_config
        rag_cfg = get_system_config().get("rag", {})
        if rag_cfg.get("enabled"):
            from .persistence.vector_store import VectorStore
            from .embedding.service import create_embedding_service
            from .router.schema_retriever import init_rag
            vs = VectorStore()
            api_key = rag_cfg.get("api_key") or state.config.llm.api_key
            emb = create_embedding_service(
                provider=rag_cfg.get("provider", "openai"),
                api_key=api_key,
                model=rag_cfg.get("model", "text-embedding-3-small"),
                api_base=rag_cfg.get("api_base") or None,
            )
            init_rag(emb, vs)
            logger.info(f"RAG initialized: provider={rag_cfg.get('provider')}, top_k={rag_cfg.get('top_k')}")
    except Exception as e:
        logger.warning(f"RAG init skipped: {e}")

    # 3. Register tools
    state.tool_registry = ToolRegistry()
    state.tool_registry.register(Tool(
        name="query_database",
        description="查询数据库。传入自然语言问题（question）会自动生成 SQL，或直接传入 SQL（sql）执行。",
        parameters={
            "question": {
                "type": "string",
                "description": "关于数据的自然语言问题，如「上月销量最高的产品是什么」（与 sql 二选一）",
            },
            "sql": {
                "type": "string",
                "description": "直接传入 SQL 查询语句执行（与 question 二选一）",
            },
        },
        required=[],
        handler=handle_query_database,
    ))

    # 4. Load all prompt categories (from DB with hardcoded fallbacks)
    from .configdb import _get_default_prompt_content
    from .configdb.base import scoped_session
    from .configdb.models.prompt import Prompt

    PROMPT_CATEGORIES = ["system", "sql_gen", "plan", "plan_reflect", "report_reflect", "schema_describe",
                         "exec_freeform", "report_gen", "report_supplement", "report_regen"]
    loaded_prompts: dict[str, str] = {}
    for cat in PROMPT_CATEGORIES:
        content = None
        try:
            with scoped_session() as session:
                row = session.query(Prompt).filter_by(name=cat, is_active=1).order_by(
                    Prompt.created_at.desc()
                ).first()
                if row:
                    content = row.content
        except Exception as e:
            logger.warning(f"Failed to load prompt '{cat}' from DB: {e}")
        if not content:
            content = _get_default_prompt_content(cat) or ""
        loaded_prompts[cat] = content

    state.sql_gen_prompt = loaded_prompts["sql_gen"]
    state.plan_prompt = loaded_prompts["plan"]
    state.plan_reflect_prompt = loaded_prompts["plan_reflect"]
    state.report_reflect_prompt = loaded_prompts["report_reflect"]
    state.schema_describe_prompt = loaded_prompts["schema_describe"]

    system_prompt = loaded_prompts["system"]
    if state.config.safety.read_only:
        system_prompt = system_prompt.replace("</rules>", "    <rule>你只能查询数据，不能修改</rule>\n  </rules>")

    logger.info("All prompt categories loaded from ConfigDB")
    logger.info("Creating ReAct agent loop...")
    state.agent_loop = SimpleAgent(
        tool_registry=state.tool_registry,
        call_llm_func=call_llm,
        system_prompt=system_prompt,
    )
    state.advanced_agent = AdvancedAgent(
        tool_registry=state.tool_registry,
        call_llm_func=call_llm,
        system_prompt=system_prompt,
        plan_prompt=loaded_prompts["plan"],
        plan_reflect_prompt=loaded_prompts["plan_reflect"],
        report_reflect_prompt=loaded_prompts["report_reflect"],
        freeform_exec_prompt=loaded_prompts["exec_freeform"],
        report_gen_prompt=loaded_prompts["report_gen"],
        report_supplement_prompt=loaded_prompts["report_supplement"],
        report_regen_prompt=loaded_prompts["report_regen"],
    )

    # 6. Session manager
    state.session_manager = SessionManager()
    logger.info(f"Shuyu ready — {len(state.session_manager._sessions)} sessions loaded")

    yield
    # (cleanup is handled by ConfigDB engine dispose in init_configdb)


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(title="Shuyu — Data Chat", lifespan=lifespan)

# CORS: allow frontend dev server and env-configured origins
import os as _os
_cors_origins = _os.environ.get("CORS_ORIGINS", "")
if _cors_origins:
    _allowed_origins = [o.strip() for o in _cors_origins.split(",")]
else:
    _allowed_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

# Mount static assets (SPA build output)
ui_dir = Path(__file__).parent.parent.parent / "ui"
ui_dist = ui_dir / "dist" if ui_dir.exists() else None
if ui_dist and ui_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(ui_dist / "assets")), name="assets")

# Register routers
app.include_router(auth_router)
app.include_router(admin_config_router)
app.include_router(schema.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(database.router)
app.include_router(config_route.router)
app.include_router(admin_stats.router)


# ---------------------------------------------------------------------------
# Root route
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = (ui_dist / "index.html") if ui_dist else None
    if index_path and index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    legacy = ui_dir / "chat.html" if ui_dir else None
    if legacy and legacy.exists():
        return HTMLResponse(legacy.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Agentic Data Analyst</h1><p>UI not found.</p>")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    cfg = load_config()
    uvicorn.run(
        app,
        host=cfg.server.host,
        port=cfg.server.port,
        reload=True,
    )
