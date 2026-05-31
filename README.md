**Shuyu (数语)** — An open-source, ChatGPT-like data analyst. Ask questions in plain language, get answers from your database. Built-in ReAct agent (no LangChain), LLM-agnostic, Song-dynasty aesthetic UI.

> ⚠️ **Work in progress** — under active development. DuckDB connector works today; more databases coming soon.

Supports DuckDB, PostgreSQL, MySQL, SQLite, Snowflake, BigQuery, Redshift, ClickHouse, MSSQL, Oracle, and any JDBC/ODBC database via connection string.

```bash
docker compose up -d
# Open http://localhost:3000 → configure → start asking
```

# 数语 (Shuyu)

> Talk to your database like ChatGPT.  
> 开源的数据库对话助手，docker compose up 就能用。

```
"上月赚了多少？"
    ↓
Agent writes SQL → queries your DB → returns answer
    ↓
"跟去年比呢？"
    ↓
Agent remembers → generates comparison SQL → shows the trend
```

## Who is this for?

**Small businesses and non-technical users** who have data in a database but can't afford a BI team.

- Warehouse inventory in DuckDB? → Agent reads it, you ask questions
- E-commerce store on Postgres? → Agent sees your tables, you ask about sales
- Want to know last month's sales? → Just type the question, no SQL needed

No training. No dashboard building. Just type what you want to know.

## Quick Start

```bash
docker compose up -d
# Open http://localhost:3000 → configure LLM + database in the right panel → start asking
```

## Features

- **Natural language queries** — ask questions in plain Chinese/English, get answers
- **Multi-turn conversation** — follow-up questions, context preserved
- **ReAct agent loop** — self-built, no heavy framework (no LangChain/LangGraph)
- **LLM-agnostic** — OpenAI, DeepSeek, Ollama, or any OpenAI-compatible API
- **Database tree** — SSMS-like tree view of tables and columns in the sidebar
- **Table filtering** — include/exclude tables by pattern (`fct_*`, `dim_*`)
- **Session history** — conversations persist across restarts (SQLite)
- **Song dynasty UI** — traditional Chinese aesthetic (ink, celadon, rice paper)

## Architecture

```
Browser (React) ──→ FastAPI ──→ ReAct Agent Loop
                                   │
                        ┌──────────┼──────────┐
                        ▼          ▼          ▼
                    SQL Tool    RAG Tool    Session
                    (DuckDB)    (ChromaDB)  Manager
                        │                     │
                        ▼                     ▼
                   analytics.db          config.db
                   (your data)           (SQLite config + history)
```

## Project Structure

```
shuyu/
├── backend/                   # FastAPI backend
│   ├── app/
│   │   ├── main.py            # API routes + startup
│   │   ├── config.py          # Default config (no YAML needed)
│   │   ├── agent/
│   │   │   ├── loop.py        # ReAct agent loop
│   │   │   └── tools/         # SQL tool, tool registry
│   │   ├── db/                # Database connectors (DuckDB, etc.)
│   │   ├── session/           # SQLite-backed session manager
│   │   └── models/            # Pydantic schemas
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                  # React + Tailwind CSS
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/        # Sidebar, Chat, ConfigPanel, etc.
│   │   ├── api/               # API client
│   │   └── types/             # TypeScript types
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml         # One-command deploy
└── docs/                      # Design specs
    ├── ui-spec.md
    └── phase1-prompt.md
```

## Configuration

No YAML files needed. All settings are configured through the web UI and persisted in SQLite:

- **LLM** — provider, API key, model, base URL
- **Database** — connection info, table filters
- **Safety** — read-only mode, data approval, max rows

Settings survive restarts.

## Database Support

| Type | Status |
|------|--------|
| DuckDB (local file) | ✅ Working |
| SQLite | ⏳ Coming soon |
| PostgreSQL | ⏳ Coming soon |
| MySQL / MariaDB | ⏳ Coming soon |
| Snowflake | 🚧 Planned |
| BigQuery | 🚧 Planned |
| Redshift | 🚧 Planned |
| ClickHouse | 🚧 Planned |
| MSSQL Server | 🚧 Planned |
| Oracle | 🚧 Planned |
| Databricks | 🚧 Planned |
| Trino / Starburst | 🚧 Planned |

Any JDBC/ODBC-compatible database can be added via a connector plugin.

> **Architecture**: Each database type is a thin connector implementing the `DatabaseConnector` interface (`backend/app/db/base.py`). Adding a new database is ~100 lines of Python.

## Tech Stack

| Component | Choice |
|-----------|--------|
| Backend | FastAPI (Python 3.11) |
| Frontend | React 18 + Tailwind CSS + Vite |
| Agent Loop | Custom ReAct (no framework) |
| Database | DuckDB (analytics) / SQLite (config + sessions) |
| Vector Store | ChromaDB |
| LLM | OpenAI / DeepSeek / Ollama / any OpenAI-compatible API |

## License

MIT — free to use, modify, and deploy.
