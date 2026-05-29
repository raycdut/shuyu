"""Agentic Data Analyst — FastAPI server entry point (slim).

App assembly: lifespan → load config/persistence → register tools → mount routes.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import state
from .agent.loop import AgentLoop
from .agent.tools.registry import Tool, ToolRegistry
from .config import load_config
from .config_store import init_sqlite, load_config_sqlite, load_db_connections_sqlite
from .llm import call_llm, handle_query_database
from .routes import chat, config as config_route, database, schema, sessions
from .session.manager import SessionManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("shuyu.main")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
    force=True,
)

for name in ("shuyu.main", "shuyu.session", "shuyu.agent", "shuyu.registry", "shuyu.db"):
    l = logging.getLogger(name)
    l.setLevel(logging.INFO)
    l.propagate = True

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Shuyu server...")

    # 1. Load config
    state.config = load_config()
    logger.info(f"Config loaded: LLM={state.config.llm.provider}/{state.config.llm.model}, DB={state.config.database.type}")

    # 2. Init SQLite persistence
    init_sqlite()
    load_config_sqlite()
    load_db_connections_sqlite()
    logger.info(f"SQLite ready: {len(state._db_connections)} DB connections loaded")

    # 3. Register tools
    state.tool_registry = ToolRegistry()
    state.tool_registry.register(Tool(
        name="query_database",
        description="用自然语言查询数据库。输入你想问的问题，我会生成 SQL 并返回查询结果。",
        parameters={
            "question": {
                "type": "string",
                "description": "关于数据的自然语言问题，如「上月销量最高的产品是什么」",
            }
        },
        handler=handle_query_database,
    ))

    # 4. Build system prompt
    system_prompt = (
        "你是一个数据分析助手。用户会问你关于数据库中数据的问题。\n\n"
        "你的工作流程：\n"
        "1. 理解用户的问题\n"
        "2. 如果需要查数据，调用 query_database 工具\n"
        "3. 根据查询结果回答用户\n"
        "4. 如果用户的问题不明确，主动澄清\n\n"
        "注意事项：\n"
        "- 如果用户问「帮我分析一下」，主动问他们想分析什么维度和时间段\n"
        "- 使用中文回答\n"
        "- 回答简洁，突出关键数据\n"
        "- 如果工具返回了数据，直接根据数据回答，不要编造"
    )
    system_prompt += f"\n- 每次查询最多返回 {state.config.safety.max_rows} 行数据"
    if state.config.safety.read_only:
        system_prompt += "\n- 你只能查询数据，不能修改"

    # 5. Create agent loop
    logger.info("Creating ReAct agent loop...")
    state.agent_loop = AgentLoop(
        tool_registry=state.tool_registry,
        call_llm_func=lambda **kw: call_llm(**kw),
        system_prompt=system_prompt,
    )

    # 6. Session manager
    state.session_manager = SessionManager(sqlite_conn=state._sqlite)
    logger.info(f"Shuyu ready — {len(state.session_manager._sessions)} sessions loaded")

    yield

    # Cleanup
    if state.connector:
        state.connector.disconnect()


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(title="Agentic Data Analyst", lifespan=lifespan)

# Mount static assets (SPA build output)
ui_dir = Path(__file__).parent.parent.parent / "ui"
ui_dist = ui_dir / "dist" if ui_dir.exists() else None
if ui_dist and ui_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(ui_dist / "assets")), name="assets")

# Register routers
app.include_router(schema.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(database.router)
app.include_router(config_route.router)


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
