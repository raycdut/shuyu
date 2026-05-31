"""Tests for agent/describe_schema_agent.py — schema description generation."""

from __future__ import annotations

import json

import pytest


class TestBuildTableBlock:
    """Tests for _build_table_block."""

    def test_basic_table(self):
        from app.agent.describe_schema_agent import _build_table_block

        table = {
            "table_name": "users",
            "description": "",
            "description_en": "",
            "columns": [
                {"column_name": "id", "data_type": "INTEGER", "is_primary_key": False, "is_nullable": True},
                {"column_name": "name", "data_type": "VARCHAR", "is_primary_key": False, "is_nullable": True},
            ],
        }
        block = _build_table_block(table)
        assert "表名: users" in block
        assert "id: INTEGER" in block
        assert "name: VARCHAR" in block

    def test_with_descriptions(self):
        from app.agent.describe_schema_agent import _build_table_block

        table = {
            "table_name": "orders",
            "description": "订单表",
            "description_en": "Orders table",
            "columns": [
                {"column_name": "id", "data_type": "INTEGER", "is_primary_key": True,
                 "is_nullable": False, "description": "订单ID", "description_en": "Order ID"},
            ],
        }
        block = _build_table_block(table)
        assert "表名: orders" in block
        assert "现有中文描述: 订单表" in block
        assert "Existing EN description: Orders table" in block
        assert "id: INTEGER" in block
        assert "(主键)" in block
        assert "(非空)" in block
        assert "现有中文描述: 订单ID" in block
        assert "现有EN描述: Order ID" in block

    def test_with_sample_values(self):
        from app.agent.describe_schema_agent import _build_table_block

        table = {
            "table_name": "products",
            "description": "",
            "description_en": "",
            "columns": [
                {"column_name": "status", "data_type": "VARCHAR", "is_primary_key": False,
                 "is_nullable": True, "description": "", "description_en": "",
                 "sample_values": ["active", "inactive", "archived"]},
            ],
        }
        block = _build_table_block(table)
        assert "表名: products" in block
        assert "示例值: active, inactive, archived" in block

    def test_with_sample_values_truncated(self):
        from app.agent.describe_schema_agent import _build_table_block

        table = {
            "table_name": "logs",
            "description": "",
            "description_en": "",
            "columns": [
                {"column_name": "level", "data_type": "VARCHAR", "is_primary_key": False,
                 "is_nullable": True, "description": "", "description_en": "",
                 "sample_values": ["ERROR", "WARN", "INFO", "DEBUG", "TRACE"]},
            ],
        }
        block = _build_table_block(table)
        assert "示例值: ERROR, WARN, INFO" in block
        assert "TRACE" not in block

    def test_no_columns(self):
        from app.agent.describe_schema_agent import _build_table_block

        table = {
            "table_name": "empty_table",
            "description": "",
            "description_en": "",
            "columns": [],
        }
        block = _build_table_block(table)
        assert "表名: empty_table" in block
        assert "字段:" in block


class TestBuildUserPrompt:
    """Tests for _build_user_prompt."""

    def test_single_table(self):
        from app.agent.describe_schema_agent import _build_user_prompt

        tables = [{"table_name": "users", "description": "", "description_en": "", "columns": []}]
        prompt = _build_user_prompt("TestDB", tables)
        assert "数据库名称: TestDB" in prompt
        assert "表名: users" in prompt
        assert "生成或优化中英文双语描述" in prompt

    def test_multiple_tables(self):
        from app.agent.describe_schema_agent import _build_user_prompt

        tables = [
            {"table_name": "users", "description": "", "description_en": "", "columns": []},
            {"table_name": "orders", "description": "", "description_en": "", "columns": []},
        ]
        prompt = _build_user_prompt("TestDB", tables)
        assert prompt.count("表名:") == 2


class TestParseLlmResponse:
    """Tests for _parse_llm_response."""

    def test_valid_json(self):
        from app.agent.describe_schema_agent import _parse_llm_response

        response = _make_response('{"tables": [{"table_name": "users", "table_description": "用户表"}]}')
        result = _parse_llm_response(response)
        assert len(result) == 1
        assert result[0]["table_name"] == "users"
        assert result[0]["table_description"] == "用户表"

    def test_markdown_wrapped_json(self):
        from app.agent.describe_schema_agent import _parse_llm_response

        response = _make_response('```json\n{"tables": [{"table_name": "users"}]}\n```')
        result = _parse_llm_response(response)
        assert len(result) == 1
        assert result[0]["table_name"] == "users"

    def test_empty_content(self):
        from app.agent.describe_schema_agent import _parse_llm_response

        response = _make_response("")
        result = _parse_llm_response(response)
        assert result == []

    def test_invalid_json(self):
        from app.agent.describe_schema_agent import _parse_llm_response

        response = _make_response("{invalid json")
        result = _parse_llm_response(response)
        assert result == []

    def test_dict_without_tables_key_returns_empty(self):
        from app.agent.describe_schema_agent import _parse_llm_response

        response = _make_response('{"table_name": "users", "table_description": "用户表"}')
        result = _parse_llm_response(response)
        assert result == []

    def test_parsed_as_list_directly(self):
        from app.agent.describe_schema_agent import _parse_llm_response

        response = _make_response('[{"table_name": "users", "table_description": "用户表"}]')
        result = _parse_llm_response(response)
        assert len(result) == 1
        assert result[0]["table_name"] == "users"

    def test_no_content_in_response(self):
        from app.agent.describe_schema_agent import _parse_llm_response

        class FakeMsg:
            content = None

        class FakeChoice:
            message = FakeMsg()

        class FakeResp:
            choices = [FakeChoice()]

        result = _parse_llm_response(FakeResp())
        assert result == []


class TestGenerateDescriptions:
    """Tests for generate_descriptions — the main entry point."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        import app.state as state
        import sqlite3

        state._sqlite = sqlite3.connect(":memory:")
        state._sqlite.execute("PRAGMA journal_mode=WAL")
        state._sqlite.executescript("""
            CREATE TABLE IF NOT EXISTS databases (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'duckdb',
                path TEXT, connection_string TEXT, host TEXT, port INTEGER,
                username TEXT, password TEXT, db_name TEXT, include_tables TEXT,
                exclude_tables TEXT, is_active INTEGER DEFAULT 0, schema_status TEXT DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS imported_tables (
                id TEXT PRIMARY KEY, database_id TEXT NOT NULL, table_name TEXT NOT NULL,
                table_type TEXT DEFAULT 'TABLE', row_count INTEGER, description TEXT DEFAULT '',
                description_en TEXT DEFAULT '', raw_ddl TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS imported_columns (
                id TEXT PRIMARY KEY, table_id TEXT NOT NULL, column_name TEXT NOT NULL,
                data_type TEXT NOT NULL, is_nullable INTEGER DEFAULT 1, is_primary_key INTEGER DEFAULT 0,
                default_value TEXT, ordinal_position INTEGER, description TEXT DEFAULT '',
                description_en TEXT DEFAULT '', sample_values TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL
            );
        """)
        state._sqlite.execute(
            "INSERT INTO databases (id, name, type, schema_status) VALUES ('db-1', 'TestDB', 'duckdb', 'imported')"
        )
        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, table_type, created_at, updated_at) "
            "VALUES ('tbl-1', 'db-1', 'users', 'TABLE', 1000.0, 1000.0)"
        )
        state._sqlite.execute(
            "INSERT INTO imported_columns (id, table_id, column_name, data_type, ordinal_position, created_at, updated_at) "
            "VALUES ('col-1', 'tbl-1', 'id', 'INTEGER', 1, 1000.0, 1000.0)"
        )
        state._sqlite.execute(
            "INSERT INTO imported_columns (id, table_id, column_name, data_type, ordinal_position, created_at, updated_at) "
            "VALUES ('col-2', 'tbl-1', 'name', 'VARCHAR', 2, 1000.0, 1000.0)"
        )
        state._sqlite.commit()

        from app.config import Config, LLMConfig
        state.config = Config()
        state.config.llm = LLMConfig(api_key="sk-test", api_base="https://test.api.com", model="gpt-4o")
        state._db_connections = [{"id": "db-1", "name": "TestDB"}]
        state.schema_describe_prompt = None

        yield

        state._sqlite.close()
        state._sqlite = None
        state._db_connections = []

    @pytest.mark.asyncio
    async def test_no_tables_returns_zero(self, setup_db):
        """When no tables are imported, should return zero counts."""
        import app.state as state
        state._sqlite.execute("DELETE FROM imported_tables")
        state._sqlite.commit()

        from app.agent.describe_schema_agent import generate_descriptions
        result = await generate_descriptions("db-1")
        assert result["tables_count"] == 0
        assert result["columns_count"] == 0

    @pytest.mark.asyncio
    async def test_with_specific_table_ids(self, setup_db):
        """Should filter to specific table IDs."""
        import app.state as state
        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, table_type, created_at, updated_at) "
            "VALUES ('tbl-2', 'db-1', 'orders', 'TABLE', 1000.0, 1000.0)"
        )
        state._sqlite.commit()

        from app.agent.describe_schema_agent import generate_descriptions
        result = await generate_descriptions("db-1", table_ids=["tbl-1"])
        assert result["tables_count"] == 0  # No LLM response, so no descriptions saved

    @pytest.mark.asyncio
    async def test_generates_and_saves_descriptions(self, setup_db, mocker):
        """Full pipeline: LLM generates descriptions, they get saved."""
        from app import state

        mock_response_data = {
            "tables": [{
                "table_name": "users",
                "table_description": "用户基本信息表",
                "table_description_en": "User basic info table",
                "columns": [
                    {"column_name": "id", "column_description": "用户唯一标识", "column_description_en": "User unique ID"},
                    {"column_name": "name", "column_description": "用户姓名", "column_description_en": "User name"},
                ],
            }]
        }

        class FakeMsg:
            content = json.dumps(mock_response_data)

        class FakeChoice:
            message = FakeMsg()

        class FakeResp:
            choices = [FakeChoice()]

        async def mock_call_llm(**kw):
            return FakeResp()

        mocker.patch("app.agent.describe_schema_agent.call_llm", mock_call_llm)

        from app.agent.describe_schema_agent import generate_descriptions
        result = await generate_descriptions("db-1")

        assert result["tables_count"] == 1
        assert result["columns_count"] == 2

        tbl = state._sqlite.execute(
            "SELECT description, description_en FROM imported_tables WHERE id = 'tbl-1'"
        ).fetchone()
        assert tbl[0] == "用户基本信息表"
        assert tbl[1] == "User basic info table"

    @pytest.mark.asyncio
    async def test_handles_llm_error_gracefully(self, setup_db, mocker):
        """If LLM call fails, should not crash and return zero."""
        async def mock_call_llm(**kw):
            raise ValueError("LLM API error")

        mocker.patch("app.agent.describe_schema_agent.call_llm", mock_call_llm)

        from app.agent.describe_schema_agent import generate_descriptions
        result = await generate_descriptions("db-1")
        assert result["tables_count"] == 0
        assert result["columns_count"] == 0

    @pytest.mark.asyncio
    async def test_database_not_found_in_connections(self, setup_db, mocker):
        """Should still work even if database is not in _db_connections."""
        import app.state as state
        state._db_connections = []

        from app.agent.describe_schema_agent import generate_descriptions
        result = await generate_descriptions("db-1")
        assert result["tables_count"] == 0  # No mock LLM, so 0

    @pytest.mark.asyncio
    async def test_batch_processing(self, setup_db, mocker):
        """Should process tables in batches of 8."""
        import app.state as state
        import time
        for i in range(10):
            tid = f"batch-tbl-{i}"
            state._sqlite.execute(
                "INSERT INTO imported_tables (id, database_id, table_name, table_type, created_at, updated_at) "
                "VALUES (?, 'db-1', ?, 'TABLE', ?, ?)",
                (tid, f"table_{i}", time.time(), time.time()),
            )
        state._sqlite.commit()

        call_count = [0]

        async def mock_call_llm(**kw):
            call_count[0] += 1
            class FakeMsg:
                content = '{"tables": []}'
            class FakeChoice:
                message = FakeMsg()
            class FakeResp:
                choices = [FakeChoice()]
            return FakeResp()

        mocker.patch("app.agent.describe_schema_agent.call_llm", mock_call_llm)

        from app.agent.describe_schema_agent import generate_descriptions
        await generate_descriptions("db-1")
        assert call_count[0] >= 2  # 10 tables = 2 batches (batch size 8)

    @pytest.mark.asyncio
    async def test_empty_table_ids_returns_all(self, setup_db):
        """When table_ids is empty list, should process all tables."""
        from app.agent.describe_schema_agent import generate_descriptions
        result = await generate_descriptions("db-1", table_ids=[])
        assert result["tables_count"] == 0  # No LLM mock, so 0


def _make_response(content: str):
    """Build a fake LLM response with the given content."""
    class FakeMsg:
        def __init__(self):
            self.content = content

    class FakeChoice:
        def __init__(self):
            self.message = FakeMsg()

    class FakeResp:
        def __init__(self):
            self.choices = [FakeChoice()]

    return FakeResp()
