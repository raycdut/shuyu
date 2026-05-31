"""Tests for app/persistence/schema.py"""

from __future__ import annotations

import sqlite3

import pytest


@pytest.fixture(autouse=True)
def setup_db():
    """Set up an in-memory SQLite database with all schema management tables."""
    import app.state as state

    state._sqlite = sqlite3.connect(":memory:")
    state._sqlite.execute("PRAGMA journal_mode=WAL")

    # Create all tables needed by persistence/schema.py
    state._sqlite.executescript("""
        CREATE TABLE IF NOT EXISTS databases (
            id                TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            type              TEXT NOT NULL DEFAULT 'duckdb',
            path              TEXT,
            connection_string TEXT,
            host              TEXT,
            port              INTEGER,
            username          TEXT,
            password          TEXT,
            db_name           TEXT,
            include_tables    TEXT,
            exclude_tables    TEXT,
            is_active         INTEGER DEFAULT 0,
            schema_status     TEXT DEFAULT 'pending'
        );

        CREATE TABLE IF NOT EXISTS imported_tables (
            id              TEXT PRIMARY KEY,
            database_id     TEXT NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
            table_name      TEXT NOT NULL,
            table_type      TEXT DEFAULT 'TABLE',
            row_count       INTEGER,
            description     TEXT DEFAULT '',
            description_en  TEXT DEFAULT '',
            raw_ddl         TEXT,
            created_at      REAL NOT NULL,
            updated_at      REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS imported_columns (
            id               TEXT PRIMARY KEY,
            table_id         TEXT NOT NULL REFERENCES imported_tables(id) ON DELETE CASCADE,
            column_name      TEXT NOT NULL,
            data_type        TEXT NOT NULL,
            is_nullable      INTEGER DEFAULT 1,
            is_primary_key   INTEGER DEFAULT 0,
            default_value    TEXT,
            ordinal_position INTEGER,
            description      TEXT DEFAULT '',
            description_en   TEXT DEFAULT '',
            sample_values    TEXT,
            created_at       REAL NOT NULL,
            updated_at       REAL NOT NULL
        );
    """)

    # Insert a mock database entry
    state._sqlite.execute(
        "INSERT INTO databases (id, name, type, schema_status) VALUES (?, ?, ?, ?)",
        ("db-test-1", "TestDB", "duckdb", "pending"),
    )
    state._sqlite.commit()

    from app.config import Config
    state.config = Config()

    yield

    if state._sqlite is not None:
        state._sqlite.close()
    state._sqlite = None


class TestLoadImportedTables:
    """Tests for load_imported_tables."""

    def test_returns_empty_list_when_sqlite_is_none(self):
        """Should return an empty list when _sqlite is None."""
        from app.persistence.schema import load_imported_tables
        import app.state as state

        state._sqlite = None
        assert load_imported_tables("db-test-1") == []

    def test_returns_empty_list_when_no_tables(self):
        """Should return an empty list when no tables exist for the database."""
        from app.persistence.schema import load_imported_tables

        result = load_imported_tables("db-test-1")
        assert result == []

    def test_returns_imported_tables(self):
        """Should return all imported tables for the given database."""
        from app.persistence.schema import load_imported_tables
        import app.state as state

        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, table_type, row_count, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 1000.0, 1000.0)",
            ("t1", "db-test-1", "users", "TABLE", 100),
        )
        state._sqlite.commit()

        result = load_imported_tables("db-test-1")
        assert len(result) == 1
        assert result[0]["id"] == "t1"
        assert result[0]["database_id"] == "db-test-1"
        assert result[0]["table_name"] == "users"
        assert result[0]["table_type"] == "TABLE"
        assert result[0]["row_count"] == 100


class TestLoadImportedColumns:
    """Tests for load_imported_columns."""

    def test_returns_empty_list_when_sqlite_is_none(self):
        """Should return an empty list when _sqlite is None."""
        from app.persistence.schema import load_imported_columns
        import app.state as state

        state._sqlite = None
        assert load_imported_columns("t1") == []

    def test_returns_empty_list_when_no_columns(self):
        """Should return an empty list when no columns exist for the table."""
        from app.persistence.schema import load_imported_columns

        result = load_imported_columns("t1")
        assert result == []

    def test_returns_imported_columns(self):
        """Should return all imported columns for the given table."""
        from app.persistence.schema import load_imported_columns
        import app.state as state

        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, created_at, updated_at) "
            "VALUES (?, ?, ?, 1000.0, 1000.0)",
            ("t1", "db-test-1", "users"),
        )
        state._sqlite.execute(
            "INSERT INTO imported_columns (id, table_id, column_name, data_type, is_nullable, is_primary_key, "
            "ordinal_position, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1000.0, 1000.0)",
            ("c1", "t1", "id", "INTEGER", 0, 1, 1),
        )
        state._sqlite.execute(
            "INSERT INTO imported_columns (id, table_id, column_name, data_type, ordinal_position, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1000.0, 1000.0)",
            ("c2", "t1", "name", "TEXT", 2),
        )
        state._sqlite.commit()

        result = load_imported_columns("t1")
        assert len(result) == 2
        assert result[0]["column_name"] == "id"
        assert result[0]["data_type"] == "INTEGER"
        assert result[0]["is_nullable"] is False
        assert result[0]["is_primary_key"] is True
        assert result[1]["column_name"] == "name"
        assert result[1]["is_primary_key"] is False

    def test_parses_sample_values_json(self):
        """Should parse sample_values JSON string into a list."""
        from app.persistence.schema import load_imported_columns
        import app.state as state

        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, created_at, updated_at) "
            "VALUES (?, ?, ?, 1000.0, 1000.0)",
            ("t2", "db-test-1", "orders"),
        )
        state._sqlite.execute(
            "INSERT INTO imported_columns (id, table_id, column_name, data_type, sample_values, "
            "ordinal_position, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, 1000.0, 1000.0)",
            ("c3", "t2", "status", "TEXT", '["active", "inactive"]'),
        )
        state._sqlite.commit()

        result = load_imported_columns("t2")
        assert result[0]["sample_values"] == ["active", "inactive"]


class TestLoadFullSchema:
    """Tests for load_full_schema."""

    def test_returns_tables_with_columns(self):
        """Should return tables with nested columns list."""
        from app.persistence.schema import load_full_schema
        import app.state as state

        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, created_at, updated_at) "
            "VALUES (?, ?, ?, 1000.0, 1000.0)",
            ("t1", "db-test-1", "users"),
        )
        state._sqlite.execute(
            "INSERT INTO imported_columns (id, table_id, column_name, data_type, "
            "ordinal_position, created_at, updated_at) VALUES (?, ?, ?, ?, 1, 1000.0, 1000.0)",
            ("c1", "t1", "id", "INTEGER"),
        )
        state._sqlite.commit()

        result = load_full_schema("db-test-1")
        assert len(result) == 1
        assert result[0]["table_name"] == "users"
        assert len(result[0]["columns"]) == 1
        assert result[0]["columns"][0]["column_name"] == "id"


class TestDeleteImportedSchema:
    """Tests for delete_imported_schema."""

    def test_deletes_tables_and_columns(self):
        """Should delete all tables and columns for the given database."""
        from app.persistence.schema import delete_imported_schema, load_imported_tables
        import app.state as state

        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, created_at, updated_at) "
            "VALUES (?, ?, ?, 1000.0, 1000.0)",
            ("t1", "db-test-1", "users"),
        )
        state._sqlite.commit()

        delete_imported_schema("db-test-1")
        assert load_imported_tables("db-test-1") == []

    def test_does_nothing_when_sqlite_is_none(self):
        """Should not crash when _sqlite is None."""
        from app.persistence.schema import delete_imported_schema
        import app.state as state

        state._sqlite = None
        delete_imported_schema("db-test-1")


class TestSaveImportedSchema:
    """Tests for save_imported_schema."""

    SAMPLE_TABLES = [
        {
            "table_name": "users",
            "table_type": "TABLE",
            "row_count": 100,
            "description": "用户表",
            "description_en": "Users table",
            "columns": [
                {
                    "column_name": "id",
                    "data_type": "INTEGER",
                    "is_nullable": False,
                    "is_primary_key": True,
                    "ordinal_position": 1,
                },
                {
                    "column_name": "name",
                    "data_type": "TEXT",
                    "is_nullable": True,
                    "ordinal_position": 2,
                },
            ],
        },
        {
            "table_name": "orders",
            "table_type": "TABLE",
            "row_count": 500,
            "columns": [
                {
                    "column_name": "order_id",
                    "data_type": "INTEGER",
                    "is_primary_key": True,
                    "ordinal_position": 1,
                },
            ],
        },
    ]

    def test_saves_and_replaces_existing(self):
        """Should save tables and columns, then replace them on the next call."""
        from app.persistence.schema import save_imported_schema, load_full_schema

        save_imported_schema("db-test-1", self.SAMPLE_TABLES)
        result = load_full_schema("db-test-1")
        assert len(result) == 2
        assert result[0]["table_name"] == "orders"  # ordered by table_name
        assert result[1]["table_name"] == "users"

        # Verify columns are included
        users = [t for t in result if t["table_name"] == "users"][0]
        assert len(users["columns"]) == 2
        assert users["columns"][0]["column_name"] == "id"
        assert users["columns"][0]["is_primary_key"] is True

        # Save again — should replace
        save_imported_schema("db-test-1", [{"table_name": "new_table", "columns": []}])
        result = load_full_schema("db-test-1")
        assert len(result) == 1
        assert result[0]["table_name"] == "new_table"

    def test_does_nothing_when_sqlite_is_none(self):
        """Should not crash when _sqlite is None."""
        from app.persistence.schema import save_imported_schema
        import app.state as state

        state._sqlite = None
        save_imported_schema("db-test-1", self.SAMPLE_TABLES)

    def test_saves_sample_values(self):
        """Should save sample_values as JSON string for columns that have them."""
        from app.persistence.schema import save_imported_schema, load_full_schema

        tables = [
            {
                "table_name": "products",
                "columns": [
                    {
                        "column_name": "category",
                        "data_type": "TEXT",
                        "sample_values": ["A", "B", "C"],
                        "ordinal_position": 1,
                    },
                ],
            },
        ]
        save_imported_schema("db-test-1", tables)
        result = load_full_schema("db-test-1")
        assert result[0]["columns"][0]["sample_values"] == ["A", "B", "C"]


class TestUpdateDescription:
    """Tests for update_description."""

    def test_updates_table_description(self):
        """Should update description and description_en for a table."""
        from app.persistence.schema import update_description, load_imported_tables
        import app.state as state

        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, created_at, updated_at) "
            "VALUES (?, ?, ?, 1000.0, 1000.0)",
            ("t1", "db-test-1", "users"),
        )
        state._sqlite.commit()

        update_description(table_id="t1", description="用户信息表", description_en="User info table")
        result = load_imported_tables("db-test-1")
        assert result[0]["description"] == "用户信息表"
        assert result[0]["description_en"] == "User info table"

    def test_updates_column_description(self):
        """Should update description and description_en for a column."""
        from app.persistence.schema import update_description, load_imported_columns
        import app.state as state

        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, created_at, updated_at) "
            "VALUES (?, ?, ?, 1000.0, 1000.0)",
            ("t1", "db-test-1", "users"),
        )
        state._sqlite.execute(
            "INSERT INTO imported_columns (id, table_id, column_name, data_type, "
            "ordinal_position, created_at, updated_at) VALUES (?, ?, ?, ?, 1, 1000.0, 1000.0)",
            ("c1", "t1", "name", "TEXT"),
        )
        state._sqlite.commit()

        update_description(column_id="c1", description="用户姓名", description_en="User name")
        result = load_imported_columns("t1")
        assert result[0]["description"] == "用户姓名"
        assert result[0]["description_en"] == "User name"

    def test_does_nothing_when_sqlite_is_none(self):
        """Should not crash when _sqlite is None."""
        from app.persistence.schema import update_description
        import app.state as state

        state._sqlite = None
        update_description(table_id="t1", description="test")


class TestUpdateDatabaseSchemaStatus:
    """Tests for update_database_schema_status."""

    def test_updates_status(self):
        """Should update the schema_status of the specified database."""
        from app.persistence.schema import update_database_schema_status
        import app.state as state

        update_database_schema_status("db-test-1", "imported")
        row = state._sqlite.execute(
            "SELECT schema_status FROM databases WHERE id = ?", ("db-test-1",)
        ).fetchone()
        assert row[0] == "imported"

    def test_does_nothing_when_sqlite_is_none(self):
        """Should not crash when _sqlite is None."""
        from app.persistence.schema import update_database_schema_status
        import app.state as state

        state._sqlite = None
        update_database_schema_status("db-test-1", "imported")


class TestGetSchemaStatus:
    """Tests for get_schema_status."""

    def test_returns_default_when_sqlite_is_none(self):
        """Should return default stats when _sqlite is None."""
        from app.persistence.schema import get_schema_status
        import app.state as state

        state._sqlite = None
        result = get_schema_status("db-test-1")
        assert result == {
            "schema_status": "pending",
            "tables_count": 0,
            "columns_count": 0,
            "described_tables": 0,
            "described_columns": 0,
        }

    def test_returns_default_when_db_not_found(self):
        """Should return pending status with zero counts when database does not exist."""
        from app.persistence.schema import get_schema_status

        result = get_schema_status("non-existent-db")
        assert result["schema_status"] == "pending"
        assert result["tables_count"] == 0

    def test_returns_correct_stats(self):
        """Should return correct tables_count, columns_count, described_tables, described_columns."""
        from app.persistence.schema import get_schema_status
        import app.state as state

        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 1000.0, 1000.0)",
            ("t1", "db-test-1", "users", "described"),
        )
        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, created_at, updated_at) "
            "VALUES (?, ?, ?, 1000.0, 1000.0)",
            ("t2", "db-test-1", "orders",),
        )
        state._sqlite.execute(
            "INSERT INTO imported_columns (id, table_id, column_name, data_type, description, "
            "ordinal_position, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, 1000.0, 1000.0)",
            ("c1", "t1", "id", "INTEGER", "primary key"),
        )
        state._sqlite.execute(
            "INSERT INTO imported_columns (id, table_id, column_name, data_type, "
            "ordinal_position, created_at, updated_at) VALUES (?, ?, ?, ?, 2, 1000.0, 1000.0)",
            ("c2", "t1", "name", "TEXT"),
        )
        state._sqlite.execute(
            "INSERT INTO imported_columns (id, table_id, column_name, data_type, "
            "ordinal_position, created_at, updated_at) VALUES (?, ?, ?, ?, 1, 1000.0, 1000.0)",
            ("c3", "t2", "order_id", "INTEGER"),
        )
        state._sqlite.commit()

        result = get_schema_status("db-test-1")
        assert result["tables_count"] == 2
        assert result["columns_count"] == 3
        assert result["described_tables"] == 1   # only t1 has description
        assert result["described_columns"] == 1   # only c1 has description

    def test_reads_database_schema_status(self):
        """Should read the schema_status from the databases table."""
        from app.persistence.schema import get_schema_status, update_database_schema_status

        update_database_schema_status("db-test-1", "completed")
        result = get_schema_status("db-test-1")
        assert result["schema_status"] == "completed"


class TestSaveDescriptions:
    """Tests for save_descriptions."""

    def test_saves_table_and_column_descriptions(self):
        """Should save descriptions for tables and columns matched by name."""
        from app.persistence.schema import save_descriptions, load_full_schema
        import app.state as state

        # First save the schema
        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, created_at, updated_at) "
            "VALUES (?, ?, ?, 1000.0, 1000.0)",
            ("t1", "db-test-1", "users"),
        )
        state._sqlite.execute(
            "INSERT INTO imported_columns (id, table_id, column_name, data_type, "
            "ordinal_position, created_at, updated_at) VALUES (?, ?, ?, ?, 1, 1000.0, 1000.0)",
            ("c1", "t1", "id", "INTEGER"),
        )
        state._sqlite.commit()

        descriptions = [
            {
                "table_name": "users",
                "table_description": "用户信息表",
                "table_description_en": "Users table",
                "columns": [
                    {
                        "column_name": "id",
                        "column_description": "用户唯一标识",
                        "column_description_en": "Unique user ID",
                    },
                ],
            },
        ]
        count = save_descriptions("db-test-1", descriptions)
        assert count == 1

        result = load_full_schema("db-test-1")
        assert result[0]["description"] == "用户信息表"
        assert result[0]["description_en"] == "Users table"
        assert result[0]["columns"][0]["description"] == "用户唯一标识"
        assert result[0]["columns"][0]["description_en"] == "Unique user ID"

    def test_skips_unknown_tables(self):
        """Should skip descriptions for tables that do not exist in the database."""
        from app.persistence.schema import save_descriptions

        descriptions = [
            {
                "table_name": "nonexistent",
                "table_description": "N/A",
                "columns": [],
            },
        ]
        count = save_descriptions("db-test-1", descriptions)
        assert count == 0

    def test_skips_columns_without_description(self):
        """Should skip columns that have no description text."""
        from app.persistence.schema import save_descriptions
        import app.state as state

        state._sqlite.execute(
            "INSERT INTO imported_tables (id, database_id, table_name, created_at, updated_at) "
            "VALUES (?, ?, ?, 1000.0, 1000.0)",
            ("t1", "db-test-1", "users"),
        )
        state._sqlite.execute(
            "INSERT INTO imported_columns (id, table_id, column_name, data_type, "
            "ordinal_position, created_at, updated_at) VALUES (?, ?, ?, ?, 1, 1000.0, 1000.0)",
            ("c1", "t1", "id", "INTEGER"),
        )
        state._sqlite.commit()

        descriptions = [
            {
                "table_name": "users",
                "table_description": "",
                "columns": [
                    {"column_name": "id", "column_description": "", "column_description_en": ""},
                ],
            },
        ]
        count = save_descriptions("db-test-1", descriptions)
        # Table has no description (empty string), but the column also has no description
        # The table won't be counted because table_description is empty
        # count will be 0 because table_desc is empty
        assert count == 0

    def test_returns_zero_when_sqlite_is_none(self):
        """Should return 0 when _sqlite is None."""
        from app.persistence.schema import save_descriptions
        import app.state as state

        state._sqlite = None
        count = save_descriptions("db-test-1", [{"table_name": "x", "table_description": "y", "columns": []}])
        assert count == 0
