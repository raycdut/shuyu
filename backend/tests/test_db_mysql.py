"""Tests for app/db/mysql.py — MySQLConnector."""

from __future__ import annotations

from unittest import mock

import pytest

from app.db.base import ColumnInfo, TableInfo


class TestMySQLConnector:
    """Tests for MySQLConnector."""

    def test_connect_success(self):
        """Should call pymysql.connect with the right parameters."""
        from app.db.mysql import MySQLConnector

        with mock.patch("app.db.mysql.pymysql.connect") as mock_connect:
            connector = MySQLConnector(
                host="127.0.0.1",
                port=3307,
                user="root",
                password="***",
                database="orders_db",
            )
            connector.connect()

        mock_connect.assert_called_once_with(
            host="127.0.0.1",
            port=3307,
            user="root",
            password="***",
            database="orders_db",
            charset="utf8mb4",
            cursorclass=mock.ANY,
        )
        assert connector._conn is not None

    def test_disconnect(self):
        """Should close the connection and set _conn to None."""
        from app.db.mysql import MySQLConnector

        mock_conn = mock.MagicMock()
        connector = MySQLConnector(database="test_db")
        connector._conn = mock_conn

        connector.disconnect()

        mock_conn.close.assert_called_once()
        assert connector._conn is None

    def test_disconnect_when_not_connected(self):
        """Should not raise when disconnect is called without a connection."""
        from app.db.mysql import MySQLConnector

        connector = MySQLConnector(database="test_db")
        connector.disconnect()  # Should not raise

    def test_test_connection_success(self):
        """Should return True when SELECT 1 succeeds."""
        from app.db.mysql import MySQLConnector

        mock_conn = mock.MagicMock()
        connector = MySQLConnector(database="test_db")
        connector._conn = mock_conn

        result = connector.test_connection()

        assert result is True
        mock_conn.execute.assert_called_with("SELECT 1")

    def test_test_connection_failure(self):
        """Should return False when connection fails."""
        from app.db.mysql import MySQLConnector

        connector = MySQLConnector(database="test_db")

        result = connector.test_connection()

        assert result is False

    def test_get_schema(self):
        """Should query information_schema and return TableInfo objects."""
        from app.db.mysql import MySQLConnector

        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Simulate two query results
        # First: list of tables
        mock_cursor.fetchall.side_effect = [
            [("customers", "BASE TABLE"), ("orders", "BASE TABLE")],
            # Columns for customers
            [
                ("customer_id", "int", "NO", "", 0, "PRI"),
                ("full_name", "varchar", "NO", "", 100, ""),
                ("email", "varchar", "YES", "", 255, ""),
            ],
            # Columns for orders
            [
                ("order_id", "int", "NO", "", 0, "PRI"),
                ("total_amount", "decimal", "YES", "", 0, ""),
                ("order_date", "datetime", "NO", "", 0, ""),
            ],
        ]

        connector = MySQLConnector(database="test_db")
        connector._conn = mock_conn

        tables = connector.get_schema()

        assert len(tables) == 2
        assert tables[0].name == "customers"
        assert len(tables[0].columns) == 3
        assert tables[0].columns[0].name == "customer_id"
        assert tables[0].columns[0].data_type == "int"
        assert tables[0].columns[0].is_primary_key is True
        assert tables[0].columns[1].name == "full_name"
        assert tables[0].columns[1].data_type == "varchar(100)"
        assert tables[0].columns[1].is_primary_key is False
        assert tables[0].columns[2].name == "email"
        assert tables[0].columns[2].data_type == "varchar(255)"

        assert tables[1].name == "orders"
        assert len(tables[1].columns) == 3
        assert tables[1].columns[0].name == "order_id"
        assert tables[1].columns[0].is_primary_key is True
        assert tables[1].columns[1].data_type == "decimal"
        assert tables[1].columns[2].data_type == "datetime"

        # Verify the SQL queries
        table_query_call = mock_cursor.execute.call_args_list[0]
        assert "information_schema.tables" in table_query_call[0][0]

    def test_get_schema_should_exclude_tables(self):
        """Should skip tables matching exclude patterns."""
        from app.db.mysql import MySQLConnector

        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.side_effect = [
            [("customers", "BASE TABLE"), ("orders", "BASE TABLE")],
            [("customer_id", "int", "NO", "", 0, "PRI")],
            [("order_id", "int", "NO", "", 0, "PRI")],
        ]

        connector = MySQLConnector(database="test_db", exclude_tables=["orders"])
        connector._conn = mock_conn

        tables = connector.get_schema()

        assert len(tables) == 1
        assert tables[0].name == "customers"

    def test_get_schema_include_only(self):
        """Should only include tables matching include patterns."""
        from app.db.mysql import MySQLConnector

        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.side_effect = [
            [("customers", "BASE TABLE"), ("orders", "BASE TABLE")],
            [("customer_id", "int", "NO", "", 0, "PRI")],
        ]

        connector = MySQLConnector(database="test_db", include_tables=["customers"])
        connector._conn = mock_conn

        tables = connector.get_schema()

        assert len(tables) == 1
        assert tables[0].name == "customers"

    def test_execute_select(self):
        """Should execute a SELECT query and return QueryResult."""
        from app.db.mysql import MySQLConnector

        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchmany.return_value = [(1, "Alice"), (2, "Bob")]

        # For the COUNT(*) subquery
        mock_cursor.fetchone.return_value = (2,)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        connector = MySQLConnector(database="test_db")
        connector._conn = mock_conn

        result = connector.execute("SELECT id, name FROM users")

        assert result.columns == ["id", "name"]
        assert result.rows == [(1, "Alice"), (2, "Bob")]
        assert result.row_count == 2

    def test_execute_empty_result(self):
        """Should handle queries that return no rows."""
        from app.db.mysql import MySQLConnector

        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.description = [("id",)]
        mock_cursor.fetchmany.return_value = []
        mock_cursor.fetchone.return_value = (0,)

        connector = MySQLConnector(database="test_db")
        connector._conn = mock_conn

        result = connector.execute("SELECT id FROM users WHERE 1=0")

        assert result.columns == ["id"]
        assert result.rows == []
        assert result.row_count == 0

    def test_format_data_type_with_length(self):
        """Should format varchar(n) and char(n) types with length."""
        from app.db.mysql import MySQLConnector

        assert MySQLConnector._format_data_type("varchar", 100) == "varchar(100)"
        assert MySQLConnector._format_data_type("char", 10) == "char(10)"
        assert MySQLConnector._format_data_type("int", 0) == "int"
        assert MySQLConnector._format_data_type("decimal", 0) == "decimal"
        assert MySQLConnector._format_data_type("text", 0) == "text"
