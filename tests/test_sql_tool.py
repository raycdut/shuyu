"""Tests for agent/tools/sql_tool.py — handle_sql_query with mock LLM and DuckDB."""

from __future__ import annotations

import duckdb
import pytest

from app.agent.tools.sql_tool import handle_sql_query
from app.db.duckdb import DuckDBConnector


@pytest.fixture(autouse=True)
def setup_sql_gen_prompt():
    """Set up sql_gen_prompt in state so handle_sql_query can access it."""
    import app.state as state
    state.sql_gen_prompt = "根据以下表结构生成 SQL。\n{schema_prompt}\n请生成 SQL 查询语句。"
    yield
    state.sql_gen_prompt = None


@pytest.fixture
def memory_db():
    """Create an in-memory DuckDB with a sample table."""
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE products (id INTEGER, name VARCHAR, price DECIMAL(10,2))")
    conn.execute("INSERT INTO products VALUES (1, '苹果', 5.00), (2, '香蕉', 3.50)")
    connector = DuckDBConnector(db_path=":memory:")
    connector._conn = conn  # inject the pre-seeded connection
    yield connector
    conn.close()


@pytest.fixture
def sample_schema():
    return "表: products\n  - id: INTEGER\n  - name: VARCHAR\n  - price: DECIMAL"


@pytest.mark.asyncio
async def test_handle_sql_query_success(memory_db, sample_schema):
    """Should execute SQL and return formatted results."""

    async def mock_llm(msgs):
        return "SELECT name, price FROM products"

    result = await handle_sql_query(
        question="有哪些产品？",
        connector=memory_db,
        schema_prompt=sample_schema,
        call_llm_func=mock_llm,
        max_rows=100,
    )
    assert "苹果" in result
    assert "香蕉" in result
    assert "5.0" in result or "5.00" in result


@pytest.mark.asyncio
async def test_handle_sql_query_unable(memory_db, sample_schema):
    """When LLM returns 'UNABLE', should return error message."""

    async def mock_llm(msgs):
        return "UNABLE: 没有找到相关表"

    result = await handle_sql_query(
        question="未知数据",
        connector=memory_db,
        schema_prompt=sample_schema,
        call_llm_func=mock_llm,
    )
    assert "无法生成 SQL" in result


@pytest.mark.asyncio
async def test_handle_sql_query_execution_error(memory_db, sample_schema):
    """When SQL execution fails, should return error with the SQL."""

    async def mock_llm(msgs):
        return "SELECT * FROM nonexistent"

    result = await handle_sql_query(
        question="查不到的表",
        connector=memory_db,
        schema_prompt=sample_schema,
        call_llm_func=mock_llm,
    )
    assert "SQL 执行失败" in result
    assert "nonexistent" in result


@pytest.mark.asyncio
async def test_handle_sql_query_strips_markdown(memory_db, sample_schema):
    """Should strip markdown SQL fences."""

    async def mock_llm(msgs):
        return "```sql\nSELECT name FROM products\n```"

    result = await handle_sql_query(
        question="产品名",
        connector=memory_db,
        schema_prompt=sample_schema,
        call_llm_func=mock_llm,
    )
    assert "苹果" in result


@pytest.mark.asyncio
async def test_create_query_database_tool(memory_db, sample_schema):
    """create_query_database_tool should return an OpenAI-compatible tool def."""
    from app.agent.tools.sql_tool import create_query_database_tool

    async def mock_llm(msgs):
        return "SELECT 1"

    tool = create_query_database_tool(memory_db, mock_llm, sample_schema)
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "query_database"
    assert "parameters" in tool["function"]
