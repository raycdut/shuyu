"""Integration tests: verify prompt changes don't break agent query pipeline.

Sets up a real DuckDB with data, configures state.sql_gen_prompt,
and runs handle_sql_query through the full pipeline to verify results.
"""

from __future__ import annotations

import duckdb
import pytest

from app.agent.tools.sql_tool import handle_sql_query
from app.db.duckdb import DuckDBConnector


SAMPLE_SQL_GEN_PROMPT = """你是一个 SQL 专家。根据用户的问题和数据库结构，生成正确的 SQL 查询。

数据库结构：
{schema_prompt}

规则：
1. 只生成 SELECT 查询
2. 只使用数据库中存在的表和字段
3. 使用中文别名（AS）让结果可读
4. 如果问题不明确，选择最合理的解释
5. 如果无法生成 SQL，回复 "UNABLE: 原因"

直接输出 SQL，不要解释。"""


@pytest.fixture
def memory_db():
    """Create an in-memory DuckDB with sample e-commerce data."""
    conn = duckdb.connect(":memory:")
    conn.execute("""
        CREATE TABLE users (
            id INTEGER, name VARCHAR, age INTEGER, city VARCHAR
        )
    """)
    conn.execute("""
        INSERT INTO users VALUES
            (1, 'Alice', 30, '北京'),
            (2, 'Bob', 25, '上海'),
            (3, 'Charlie', 35, '北京'),
            (4, 'Diana', 28, '深圳')
    """)
    conn.execute("""
        CREATE TABLE orders (
            id INTEGER, user_id INTEGER, product VARCHAR, amount DECIMAL(10,2), qty INTEGER
        )
    """)
    conn.execute("""
        INSERT INTO orders VALUES
            (1, 1, '笔记本电脑', 6999.00, 1),
            (2, 1, '鼠标', 99.00, 2),
            (3, 2, '键盘', 299.00, 1),
            (4, 3, '显示器', 1999.00, 1),
            (5, 3, '鼠标', 99.00, 1),
            (6, 4, '笔记本电脑', 6999.00, 1)
    """)
    connector = DuckDBConnector(db_path=":memory:")
    connector._conn = conn
    yield connector
    conn.close()


@pytest.fixture
def sample_schema():
    return "表: users (id, name, age, city)\n表: orders (id, user_id, product, amount, qty)"


def test_prompt_integration_default_prompt(memory_db, sample_schema):
    """Verify default (seeded) sql_gen prompt still works correctly."""

    async def mock_llm(msgs):
        # Verify the system prompt contains expected instructions
        system_msg = msgs[0]
        assert system_msg["role"] == "system"
        assert "SQL 专家" in system_msg["content"]
        assert "users" in system_msg["content"] or "orders" in system_msg["content"]
        # Return a valid SQL
        return "SELECT name FROM users WHERE city = '北京'"

    import app.state as state
    from app.persistence import SQL_GEN_PROMPT
    # Set the default seeded sql_gen_prompt
    original = state.sql_gen_prompt
    state.sql_gen_prompt = SQL_GEN_PROMPT
    try:
        result = handle_sql_query(
            question="北京的用户有哪些？",
            connector=memory_db,
            schema_prompt=sample_schema,
            call_llm_func=mock_llm,
            max_rows=100,
        )
        # The result is a Future since handle_sql_query is async
        import asyncio
        actual = asyncio.run(result)
        assert "Alice" in actual or "Alice" in str(actual)
        assert "Charlie" in actual or "Charlie" in str(actual)
    finally:
        state.sql_gen_prompt = original


def test_prompt_integration_custom_prompt(memory_db, sample_schema):
    """Verify custom sql_gen_prompt from state is used correctly."""

    captured_content = []

    async def mock_llm(msgs):
        system_msg = msgs[0]
        assert system_msg["role"] == "system"
        captured_content.append(system_msg["content"])
        # Verify the schema was injected into the template
        assert "users" in system_msg["content"]
        assert "orders" in system_msg["content"]
        # Our custom prompt uses different wording
        assert "SQL 专家" in system_msg["content"]
        return "SELECT product, SUM(amount) as 总金额 FROM orders GROUP BY product ORDER BY 总金额 DESC"

    import app.state as state
    original = state.sql_gen_prompt
    state.sql_gen_prompt = SAMPLE_SQL_GEN_PROMPT
    try:
        import asyncio
        result = asyncio.run(
            handle_sql_query(
                question="每种产品的销售总额？",
                connector=memory_db,
                schema_prompt=sample_schema,
                call_llm_func=mock_llm,
                max_rows=100,
            )
        )
        assert "笔记本电脑" in result
        assert "13998" in result or "13998.0" in result
        assert len(captured_content) == 1
        # Verify the prompt was formatted with the schema
        assert sample_schema in captured_content[0]
    finally:
        state.sql_gen_prompt = original


def test_prompt_integration_dynamic_prompt_update(memory_db, sample_schema):
    """Verify changing state.sql_gen_prompt mid-flight works correctly."""

    async def mock_llm_v1(msgs):
        return "SELECT name FROM users WHERE age > 30"

    async def mock_llm_v2(msgs):
        return "SELECT name FROM users WHERE age > 25"

    import app.state as state
    from app.persistence import SQL_GEN_PROMPT
    import asyncio

    original = state.sql_gen_prompt

    # Test with default seeded prompt
    state.sql_gen_prompt = SQL_GEN_PROMPT
    result1 = asyncio.run(
        handle_sql_query(
            question="30岁以上用户？",
            connector=memory_db,
            schema_prompt=sample_schema,
            call_llm_func=mock_llm_v1,
        )
    )
    assert "Charlie" in result1

    # Switch to custom prompt
    state.sql_gen_prompt = SAMPLE_SQL_GEN_PROMPT
    result2 = asyncio.run(
        handle_sql_query(
            question="25岁以上用户？",
            connector=memory_db,
            schema_prompt=sample_schema,
            call_llm_func=mock_llm_v2,
        )
    )
    assert "Alice" in result2
    assert "Charlie" in result2

    state.sql_gen_prompt = original


def test_prompt_integration_sql_execution_with_join(memory_db, sample_schema):
    """Verify complex queries (JOIN) work end-to-end with custom prompt."""

    async def mock_llm(msgs):
        return """
        SELECT u.name, u.city, SUM(o.amount) as 总消费
        FROM users u
        JOIN orders o ON u.id = o.user_id
        GROUP BY u.name, u.city
        ORDER BY 总消费 DESC
        """

    import app.state as state
    import asyncio

    original = state.sql_gen_prompt
    state.sql_gen_prompt = SAMPLE_SQL_GEN_PROMPT
    try:
        result = asyncio.run(
            handle_sql_query(
                question="每个用户的总消费？",
                connector=memory_db,
                schema_prompt=sample_schema,
                call_llm_func=mock_llm,
                max_rows=100,
            )
        )
        # Alice: 6999 + 99 = 7098, Bob: 299, Charlie: 1999+99=2098, Diana: 6999
        assert "Alice" in result
        assert "Charlie" in result
        assert "7098" in result or "7098.0" in result
        assert "2098" in result or "2098.0" in result
    finally:
        state.sql_gen_prompt = original


def test_prompt_integration_prompt_template_formatting(memory_db, sample_schema):
    """Verify the template {schema_prompt} variable is correctly substituted."""

    custom_template = "## CUSTOM SQL PROMPT\n\nSchema:\n{schema_prompt}\n\nGenerate SQL:"

    async def mock_llm(msgs):
        content = msgs[0]["content"]
        assert "CUSTOM SQL PROMPT" in content
        assert "users" in content
        assert "orders" in content
        # The schema should be injected into the {schema_prompt} placeholder
        assert sample_schema in content
        return "SELECT COUNT(*) as cnt FROM users"

    import app.state as state
    import asyncio

    original = state.sql_gen_prompt
    state.sql_gen_prompt = custom_template
    try:
        result = asyncio.run(
            handle_sql_query(
                question="有多少用户？",
                connector=memory_db,
                schema_prompt=sample_schema,
                call_llm_func=mock_llm,
            )
        )
        assert "4" in result
    finally:
        state.sql_gen_prompt = original
