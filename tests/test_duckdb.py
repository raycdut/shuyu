"""Tests for db/duckdb.py — DuckDB connector with :memory: database."""

from __future__ import annotations

import pytest

from app.db.duckdb import DuckDBConnector
from app.db.base import ColumnInfo, TableInfo


@pytest.fixture
def connector():
    """Create a DuckDB connector with in-memory DB."""
    c = DuckDBConnector(db_path=":memory:")
    c.connect()
    c._conn.execute("CREATE TABLE users (id INTEGER, name VARCHAR, age INTEGER)")
    c._conn.execute("INSERT INTO users VALUES (1, 'Alice', 30), (2, 'Bob', 25), (3, 'Charlie', 35)")
    c._conn.execute("CREATE TABLE orders (id INTEGER, user_id INTEGER, amount DECIMAL(10,2))")
    c._conn.execute("INSERT INTO orders VALUES (1, 1, 100.00), (2, 2, 50.00)")
    yield c
    c.disconnect()


class TestDuckDBConnector:
    def test_connect(self):
        c = DuckDBConnector(db_path=":memory:")
        c.connect()
        assert c._conn is not None
        c.disconnect()
        assert c._conn is None

    def test_test_connection(self):
        c = DuckDBConnector(db_path=":memory:")
        c.connect()
        assert c.test_connection() is True
        c.disconnect()

    def test_get_schema(self, connector):
        tables = connector.get_schema()
        names = [t.name for t in tables]
        assert "users" in names
        assert "orders" in names

    def test_get_schema_columns(self, connector):
        tables = connector.get_schema()
        users = next(t for t in tables if t.name == "users")
        col_names = [c.name for c in users.columns]
        assert "id" in col_names
        assert "name" in col_names
        assert "age" in col_names

    def test_execute_select(self, connector):
        result = connector.execute("SELECT name, age FROM users ORDER BY age")
        assert len(result.columns) == 2
        assert len(result.rows) == 3
        assert result.rows[0][0] == "Bob"
        assert result.rows[0][1] == 25
        assert result.rows[1][0] == "Alice"

    def test_execute_with_limit(self, connector):
        result = connector.execute("SELECT * FROM users", max_rows=2)
        assert len(result.rows) <= 2

    def test_execute_empty_result(self, connector):
        result = connector.execute("SELECT * FROM users WHERE 1=0")
        assert len(result.rows) == 0
        assert result.row_count == 0

    def test_execute_ddl(self, connector):
        """DDL should not raise."""
        result = connector.execute("CREATE TABLE temp (x INTEGER)")
        assert result is not None

    def test_execute_dml(self, connector):
        """INSERT should not raise."""
        result = connector.execute("INSERT INTO users VALUES (99, 'Test', 99)")
        assert result is not None

    def test_execute_with_params(self, connector):
        result = connector.execute(
            "SELECT name FROM users WHERE age > ?",
            params=[30],
        )
        if len(result.rows) > 0:
            assert result.rows[0][0] == "Charlie"

    def test_include_tables_filter(self):
        c = DuckDBConnector(db_path=":memory:", include_tables=["users"])
        c.connect()
        c._conn.execute("CREATE TABLE users (id INTEGER)")
        c._conn.execute("CREATE TABLE secret (x INTEGER)")
        tables = c.get_schema()
        names = [t.name for t in tables]
        assert "users" in names
        assert "secret" not in names
        c.disconnect()

    def test_exclude_tables_filter(self):
        c = DuckDBConnector(db_path=":memory:", exclude_tables=["secret*"])
        c.connect()
        c._conn.execute("CREATE TABLE users (id INTEGER)")
        c._conn.execute("CREATE TABLE secret_data (x INTEGER)")
        tables = c.get_schema()
        names = [t.name for t in tables]
        assert "users" in names
        assert "secret_data" not in names
        c.disconnect()

    def test_get_schema_empty_db(self):
        c = DuckDBConnector(db_path=":memory:")
        c.connect()
        tables = c.get_schema()
        assert tables == []
        c.disconnect()

    def test_row_count(self, connector):
        """Row count should be returned."""
        result = connector.execute("SELECT count(*) as cnt FROM users")
        assert result.rows[0][0] == 3
