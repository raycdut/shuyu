"""Tests for app/db/postgresql.py — PostgreSQLConnector."""

from __future__ import annotations

from unittest import mock

import pytest

from app.db.base import ColumnInfo, TableInfo


class TestPostgreSQLConnector:
    """Tests for PostgreSQLConnector."""

    def test_connect_success(self):
        """Should call psycopg2.connect with the right parameters."""
        from app.db.postgresql import PostgreSQLConnector

        with mock.patch("app.db.postgresql.psycopg2.connect") as mock_connect:
            connector = PostgreSQLConnector(
                host="127.0.0.1",
                port=5433,
                user="postgres",
                password="secret",
                database="crm_db",
            )
            connector.connect()

        mock_connect.assert_called_once_with(
            host="127.0.0.1",
            port=5433,
            user="postgres",
            password="secret",
            dbname="crm_db",
        )
        assert connector._conn is not None

    def test_disconnect(self):
        """Should close the connection and set _conn to None."""
        from app.db.postgresql import PostgreSQLConnector

        mock_conn = mock.MagicMock()
        connector = PostgreSQLConnector(database="test_db")
        connector._conn = mock_conn

        connector.disconnect()

        mock_conn.close.assert_called_once()
        assert connector._conn is None

    def test_disconnect_when_not_connected(self):
        """Should not raise when disconnect is called without a connection."""
        from app.db.postgresql import PostgreSQLConnector

        connector = PostgreSQLConnector(database="test_db")
        connector.disconnect()

    def test_test_connection_success(self):
        """Should return True when SELECT 1 succeeds."""
        from app.db.postgresql import PostgreSQLConnector

        mock_conn = mock.MagicMock()
        connector = PostgreSQLConnector(database="test_db")
        connector._conn = mock_conn

        result = connector.test_connection()

        assert result is True

    def test_test_connection_failure(self):
        """Should return False when connection fails."""
        from app.db.postgresql import PostgreSQLConnector

        connector = PostgreSQLConnector(database="test_db")

        result = connector.test_connection()

        assert result is False

    def test_get_schema(self):
        """Should query information_schema and return TableInfo objects."""
        from app.db.postgresql import PostgreSQLConnector

        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Simulate query results using RealDictCursor-style dict rows
        mock_cursor.fetchall.side_effect = [
            # Tables
            [
                {"table_name": "customers", "table_type": "BASE TABLE"},
                {"table_name": "orders", "table_type": "BASE TABLE"},
            ],
            # Columns for customers
            [
                {"column_name": "customer_id", "data_type": "integer", "is_nullable": "NO",
                 "character_maximum_length": None, "constraint_type": "PRIMARY KEY"},
                {"column_name": "full_name", "data_type": "character varying", "is_nullable": "NO",
                 "character_maximum_length": 100, "constraint_type": ""},
                {"column_name": "email", "data_type": "character varying", "is_nullable": "YES",
                 "character_maximum_length": 255, "constraint_type": ""},
            ],
            # Columns for orders
            [
                {"column_name": "order_id", "data_type": "integer", "is_nullable": "NO",
                 "character_maximum_length": None, "constraint_type": "PRIMARY KEY"},
                {"column_name": "total_amount", "data_type": "numeric", "is_nullable": "YES",
                 "character_maximum_length": None, "constraint_type": ""},
                {"column_name": "order_date", "data_type": "timestamp without time zone", "is_nullable": "NO",
                 "character_maximum_length": None, "constraint_type": ""},
            ],
        ]

        connector = PostgreSQLConnector(database="test_db")
        connector._conn = mock_conn

        tables = connector.get_schema()

        assert len(tables) == 2
        assert tables[0].name == "customers"
        assert len(tables[0].columns) == 3
        assert tables[0].columns[0].name == "customer_id"
        assert tables[0].columns[0].data_type == "integer"
        assert tables[0].columns[0].is_primary_key is True
        assert tables[0].columns[1].name == "full_name"
        assert tables[0].columns[1].data_type == "character varying(100)"
        assert tables[0].columns[1].is_primary_key is False
        assert tables[0].columns[2].name == "email"
        assert tables[0].columns[2].data_type == "character varying(255)"

        assert tables[1].name == "orders"
        assert len(tables[1].columns) == 3
        assert tables[1].columns[0].name == "order_id"
        assert tables[1].columns[0].is_primary_key is True
        assert tables[1].columns[1].data_type == "numeric"
        assert tables[1].columns[2].data_type == "timestamp without time zone"

        # Verify the SQL queries
        table_query_call = mock_cursor.execute.call_args_list[0]
        assert "information_schema.tables" in table_query_call[0][0]

    def test_get_schema_should_exclude_tables(self):
        """Should skip tables matching exclude patterns."""
        from app.db.postgresql import PostgreSQLConnector

        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.side_effect = [
            [
                {"table_name": "customers", "table_type": "BASE TABLE"},
                {"table_name": "orders", "table_type": "BASE TABLE"},
            ],
            [
                {"column_name": "customer_id", "data_type": "integer", "is_nullable": "NO",
                 "character_maximum_length": None, "constraint_type": "PRIMARY KEY"},
            ],
        ]

        connector = PostgreSQLConnector(database="test_db", exclude_tables=["orders"])
        connector._conn = mock_conn

        tables = connector.get_schema()

        assert len(tables) == 1
        assert tables[0].name == "customers"

    def test_get_schema_include_only(self):
        """Should only include tables matching include patterns."""
        from app.db.postgresql import PostgreSQLConnector

        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.side_effect = [
            [
                {"table_name": "customers", "table_type": "BASE TABLE"},
                {"table_name": "orders", "table_type": "BASE TABLE"},
            ],
            [
                {"column_name": "customer_id", "data_type": "integer", "is_nullable": "NO",
                 "character_maximum_length": None, "constraint_type": "PRIMARY KEY"},
            ],
        ]

        connector = PostgreSQLConnector(database="test_db", include_tables=["customers"])
        connector._conn = mock_conn

        tables = connector.get_schema()

        assert len(tables) == 1
        assert tables[0].name == "customers"

    def test_execute_select(self):
        """Should execute a SELECT query and return QueryResult."""
        from app.db.postgresql import PostgreSQLConnector

        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_desc = mock.MagicMock()
        mock_desc.name = "id"
        mock_desc2 = mock.MagicMock()
        mock_desc2.name = "name"
        mock_cursor.description = [mock_desc, mock_desc2]

        mock_cursor.fetchmany.return_value = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]

        mock_cursor.fetchone.return_value = {"cnt": 2}

        connector = PostgreSQLConnector(database="test_db")
        connector._conn = mock_conn

        result = connector.execute("SELECT id, name FROM users")

        assert result.columns == ["id", "name"]
        assert result.rows == [[1, "Alice"], [2, "Bob"]]
        assert result.row_count == 2

    def test_execute_empty_result(self):
        """Should handle queries that return no rows."""
        from app.db.postgresql import PostgreSQLConnector

        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_desc = mock.MagicMock()
        mock_desc.name = "id"
        mock_cursor.description = [mock_desc]
        mock_cursor.fetchmany.return_value = []
        mock_cursor.fetchone.return_value = {"cnt": 0}

        connector = PostgreSQLConnector(database="test_db")
        connector._conn = mock_conn

        result = connector.execute("SELECT id FROM users WHERE 1=0")

        assert result.columns == ["id"]
        assert result.rows == []
        assert result.row_count == 0

    def test_format_data_type_with_length(self):
        """Should format varchar/character types with length."""
        from app.db.postgresql import PostgreSQLConnector

        assert PostgreSQLConnector._format_data_type("character varying", 100) == "character varying(100)"
        assert PostgreSQLConnector._format_data_type("varchar", 50) == "varchar(50)"
        assert PostgreSQLConnector._format_data_type("character", 10) == "character(10)"
        assert PostgreSQLConnector._format_data_type("char", 5) == "char(5)"
        assert PostgreSQLConnector._format_data_type("integer", None) == "integer"
        assert PostgreSQLConnector._format_data_type("numeric", None) == "numeric"
        assert PostgreSQLConnector._format_data_type("text", None) == "text"
