"""Tests for app/persistence/schema.py"""

from __future__ import annotations


import pytest


@pytest.fixture(autouse=True)
def setup_db():
    """Seed a databases row for foreign-key references."""
    from app.configdb.base import scoped_session
    from app.configdb.models.database import DatabaseConnection

    with scoped_session() as s:
        existing = s.query(DatabaseConnection).filter_by(id="db-test-1").first()
        if not existing:
            s.add(DatabaseConnection(
                id="db-test-1", name="TestDB", type="duckdb", schema_status="pending",
            ))

    yield


class TestLoadImportedTables:
    """Tests for load_imported_tables."""

    def test_returns_empty_list_when_sqlite_is_none(self):
        """Should return an empty list when _sqlite is None."""
        from app.persistence.schema import load_imported_tables
        import app.state as state

        state._sqlite = None
        state._configdb_session_factory = None
        assert load_imported_tables("db-test-1") == []

    def test_returns_empty_list_when_no_tables(self):
        """Should return an empty list when no tables exist for the database."""
        from app.persistence.schema import load_imported_tables

        result = load_imported_tables("db-test-1")
        assert result == []

    def test_returns_imported_tables(self):
        """Should return all imported tables for the given database."""
        from app.persistence.schema import load_imported_tables
        from app.configdb.base import scoped_session
        from app.configdb.models.schema import ImportedTable

        with scoped_session() as s:
            s.add(ImportedTable(
                id="t1", database_id="db-test-1", table_name="users",
                table_type="TABLE", row_count=100, created_at=1000.0, updated_at=1000.0,
            ))

        result = load_imported_tables("db-test-1")
        assert len(result) == 1
        assert result[0]["table_name"] == "users"
        assert result[0]["row_count"] == 100

    def test_returns_only_tables_for_specified_database(self):
        """Should filter results by database_id."""
        from app.persistence.schema import load_imported_tables
        from app.configdb.base import scoped_session
        from app.configdb.models.schema import ImportedTable

        with scoped_session() as s:
            s.add(ImportedTable(
                id="t1", database_id="db-test-1", table_name="users",
                table_type="TABLE", row_count=100, created_at=1000.0, updated_at=1000.0,
            ))
            s.add(ImportedTable(
                id="t2", database_id="other-db", table_name="products",
                table_type="TABLE", row_count=50, created_at=1000.0, updated_at=1000.0,
            ))

        result = load_imported_tables("db-test-1")
        assert len(result) == 1
        assert result[0]["table_name"] == "users"

        result2 = load_imported_tables("other-db")
        assert len(result2) == 1
        assert result2[0]["table_name"] == "products"


class TestLoadImportedColumns:
    """Tests for load_imported_columns."""

    def test_returns_empty_list_when_sqlite_is_none(self):
        """Should return an empty list when _sqlite is None."""
        from app.persistence.schema import load_imported_columns
        import app.state as state

        state._sqlite = None
        state._configdb_session_factory = None
        assert load_imported_columns("table-1") == []

    def test_returns_imported_columns(self):
        """Should return all imported columns for the given table."""
        from app.persistence.schema import load_imported_columns
        from app.configdb.base import scoped_session
        from app.configdb.models.schema import ImportedTable, ImportedColumn

        with scoped_session() as s:
            s.add(ImportedTable(
                id="t1", database_id="db-test-1", table_name="users",
                table_type="TABLE", row_count=100, created_at=1000.0, updated_at=1000.0,
            ))
            s.add(ImportedColumn(
                id="c1", table_id="t1", column_name="id", data_type="INTEGER",
                ordinal_position=1, created_at=1000.0, updated_at=1000.0,
            ))
            s.add(ImportedColumn(
                id="c2", table_id="t1", column_name="name", data_type="TEXT",
                ordinal_position=2, created_at=1000.0, updated_at=1000.0,
            ))

        result = load_imported_columns("t1")
        assert len(result) == 2
        assert result[0]["column_name"] == "id"
        assert result[1]["column_name"] == "name"


class TestLoadFullSchema:
    """Tests for load_full_schema."""

    def test_returns_tables_with_columns(self):
        """Should return tables with nested columns."""
        from app.persistence.schema import load_full_schema
        from app.configdb.base import scoped_session
        from app.configdb.models.schema import ImportedTable, ImportedColumn

        with scoped_session() as s:
            s.add(ImportedTable(
                id="t1", database_id="db-test-1", table_name="users",
                table_type="TABLE", row_count=100, created_at=1000.0, updated_at=1000.0,
            ))
            s.add(ImportedColumn(
                id="c1", table_id="t1", column_name="id", data_type="INTEGER",
                ordinal_position=1, created_at=1000.0, updated_at=1000.0,
            ))

        result = load_full_schema("db-test-1")
        assert len(result) == 1
        assert result[0]["table_name"] == "users"
        assert len(result[0]["columns"]) == 1
        assert result[0]["columns"][0]["column_name"] == "id"


class TestSaveImportedSchema:
    """Tests for save_imported_schema."""

    def test_saves_tables_and_columns(self):
        """Should save tables and columns, replacing existing data."""
        from app.persistence.schema import save_imported_schema, load_full_schema
        from app.configdb.base import scoped_session
        from app.configdb.models.schema import ImportedTable

        with scoped_session() as s:
            s.add(ImportedTable(
                id="old", database_id="db-test-1", table_name="old_table",
                table_type="TABLE", row_count=10, created_at=500.0, updated_at=500.0,
            ))

        new_tables = [
            {
                "table_name": "products",
                "table_type": "TABLE",
                "row_count": 200,
                "columns": [
                    {"column_name": "id", "data_type": "INTEGER", "ordinal_position": 1},
                    {"column_name": "name", "data_type": "TEXT", "ordinal_position": 2},
                ],
            }
        ]
        save_imported_schema("db-test-1", new_tables)

        result = load_full_schema("db-test-1")
        assert len(result) == 1
        assert result[0]["table_name"] == "products"
        assert len(result[0]["columns"]) == 2


class TestDeleteImportedSchema:
    """Tests for delete_imported_schema."""

    def test_deletes_tables_and_columns(self):
        """Should delete all tables and columns for a database."""
        from app.persistence.schema import delete_imported_schema, load_full_schema
        from app.configdb.base import scoped_session
        from app.configdb.models.schema import ImportedTable, ImportedColumn

        with scoped_session() as s:
            s.add(ImportedTable(
                id="t1", database_id="db-test-1", table_name="users",
                table_type="TABLE", row_count=100, created_at=1000.0, updated_at=1000.0,
            ))
            s.add(ImportedColumn(
                id="c1", table_id="t1", column_name="id", data_type="INTEGER",
                created_at=1000.0, updated_at=1000.0,
            ))

        delete_imported_schema("db-test-1")
        assert load_full_schema("db-test-1") == []


class TestUpdateDescription:
    """Tests for update_description."""

    def test_updates_table_description(self):
        """Should update the description of a table."""
        from app.persistence.schema import update_description, load_imported_tables
        from app.configdb.base import scoped_session
        from app.configdb.models.schema import ImportedTable

        with scoped_session() as s:
            s.add(ImportedTable(
                id="t1", database_id="db-test-1", table_name="users",
                table_type="TABLE", row_count=100, created_at=1000.0, updated_at=1000.0,
            ))

        update_description(table_id="t1", description="用户表", description_en="Users table")

        tables = load_imported_tables("db-test-1")
        assert tables[0]["description"] == "用户表"
        assert tables[0]["description_en"] == "Users table"


class TestGetSchemaStatus:
    """Tests for get_schema_status."""

    def test_returns_pending_when_no_database(self):
        """Should return pending status when database not found."""
        from app.persistence.schema import get_schema_status

        result = get_schema_status("non-existent")
        assert result["schema_status"] == "pending"

    def test_returns_status_with_counts(self):
        """Should return schema status with table/column counts."""
        from app.persistence.schema import get_schema_status
        from app.configdb.base import scoped_session
        from app.configdb.models.schema import ImportedTable, ImportedColumn

        with scoped_session() as s:
            s.add(ImportedTable(
                id="t1", database_id="db-test-1", table_name="users",
                table_type="TABLE", row_count=100, description="用户",
                created_at=1000.0, updated_at=1000.0,
            ))
            s.add(ImportedColumn(
                id="c1", table_id="t1", column_name="id", data_type="INTEGER",
                description="主键", created_at=1000.0, updated_at=1000.0,
            ))

        result = get_schema_status("db-test-1")
        assert result["tables_count"] == 1
        assert result["columns_count"] == 1
        assert result["described_tables"] == 1
        assert result["described_columns"] == 1
