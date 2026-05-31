"""Tests for app/db/schema.py"""

from __future__ import annotations

import sqlite3
from unittest import mock

import pytest

from app.db.base import ColumnInfo, TableInfo


@pytest.fixture(autouse=True)
def setup_state():
    """Set up app.state with a basic config for all tests."""
    import app.state as state

    from app.config import Config
    state.config = Config()

    yield


class TestBuildSchemaPrompt:
    """Tests for build_schema_prompt."""

    def test_with_tables_and_no_db_id(self):
        """Should format tables and columns without descriptions when no db_id is given."""
        from app.db.schema import build_schema_prompt

        tables = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo(name="id", data_type="INTEGER"),
                    ColumnInfo(name="name", data_type="TEXT"),
                ],
            ),
        ]

        result = build_schema_prompt(tables)
        assert "以下是数据库中的表和字段：" in result
        assert "表: users" in result
        assert "id: INTEGER" in result
        assert "name: TEXT" in result
        assert "PK" not in result

    def test_with_primary_keys(self):
        """Should mark primary key columns with (PK) in the output."""
        from app.db.schema import build_schema_prompt

        tables = [
            TableInfo(
                name="orders",
                columns=[
                    ColumnInfo(name="order_id", data_type="INTEGER", is_primary_key=True),
                    ColumnInfo(name="amount", data_type="FLOAT"),
                ],
            ),
        ]

        result = build_schema_prompt(tables)
        assert "order_id: INTEGER (PK)" in result
        assert "amount: FLOAT" in result

    def test_with_descriptions_from_persistence(self):
        """Should include table and column descriptions loaded from persistence when db_id is given."""
        from app.db.schema import build_schema_prompt

        tables = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo(name="id", data_type="INTEGER"),
                    ColumnInfo(name="email", data_type="TEXT", comment="Email address"),
                ],
            ),
        ]

        # Mock _load_dynamic_descriptions to return predefined descriptions
        fake_descriptions = {
            "users": {
                "description": "用户信息表",
                "description_en": "Users table",
                "columns": {"id": "用户唯一标识", "email": "电子邮箱"},
                "columns_en": {"id": "Unique ID", "email": "Email address"},
            },
        }

        with mock.patch("app.db.schema._load_dynamic_descriptions", return_value=fake_descriptions):
            result = build_schema_prompt(tables, db_id="db-1")

        assert "描述: 用户信息表" in result
        assert "Description: Users table" in result
        assert "id: INTEGER — 用户唯一标识 (Unique ID)" in result
        # The comment from ColumnInfo should be overridden by dynamic descriptions
        assert "email: TEXT — 电子邮箱 (Email address)" in result

    def test_without_table_descriptions(self):
        """Should not add description lines when descriptions dict is empty for a table."""
        from app.db.schema import build_schema_prompt

        tables = [
            TableInfo(
                name="empty_desc",
                columns=[
                    ColumnInfo(name="col1", data_type="TEXT"),
                ],
            ),
        ]

        fake_descriptions = {
            "empty_desc": {
                "description": "",
                "description_en": "",
                "columns": {},
                "columns_en": {},
            },
        }

        with mock.patch("app.db.schema._load_dynamic_descriptions", return_value=fake_descriptions):
            result = build_schema_prompt(tables, db_id="db-1")

        assert "描述:" not in result
        assert "col1: TEXT" in result

    def test_with_no_columns(self):
        """Should handle tables with no columns gracefully."""
        from app.db.schema import build_schema_prompt

        tables = [
            TableInfo(name="empty_table", columns=[]),
        ]

        result = build_schema_prompt(tables)
        assert "表: empty_table" in result

    def test_multiple_tables(self):
        """Should format multiple tables in order."""
        from app.db.schema import build_schema_prompt

        tables = [
            TableInfo(name="a_table", columns=[ColumnInfo(name="id", data_type="INT")]),
            TableInfo(name="b_table", columns=[ColumnInfo(name="val", data_type="TEXT")]),
        ]

        result = build_schema_prompt(tables)
        # a_table should come before b_table
        assert result.index("表: a_table") < result.index("表: b_table")


class TestBuildSchemaLight:
    """Tests for build_schema_light."""

    def test_with_tables(self):
        """Should format a brief summary of available tables and their columns."""
        from app.db.schema import build_schema_light

        tables = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo(name="id", data_type="INTEGER"),
                    ColumnInfo(name="name", data_type="TEXT"),
                ],
            ),
        ]

        result = build_schema_light(tables)
        assert "可用表：" in result
        assert "users(id, name)" in result

    def test_with_empty_tables(self):
        """Should return a fallback message when the table list is empty."""
        from app.db.schema import build_schema_light

        result = build_schema_light([])
        assert result == "当前无可查数据"

    def test_truncates_long_column_lists(self):
        """Should truncate column lists longer than 8 with an ellipsis."""
        from app.db.schema import build_schema_light

        columns = [ColumnInfo(name=f"col{i}", data_type="TEXT") for i in range(12)]
        tables = [TableInfo(name="wide_table", columns=columns)]

        result = build_schema_light(tables)
        assert "col0" in result
        assert "col7" in result
        assert "..." in result
        # col8 should not appear (only first 8)
        assert "col8" not in result.split("...")[0] if "..." in result else True

    def test_with_descriptions(self):
        """Should include table descriptions when available."""
        from app.db.schema import build_schema_light

        tables = [
            TableInfo(
                name="users",
                columns=[ColumnInfo(name="id", data_type="INTEGER")],
            ),
        ]

        fake_descriptions = {
            "users": {
                "description": "用户信息表",
                "description_en": "",
                "columns": {},
                "columns_en": {},
            },
        }

        with mock.patch("app.db.schema._load_dynamic_descriptions", return_value=fake_descriptions):
            result = build_schema_light(tables, db_id="db-1")

        assert "users(id) — 用户信息表" in result

    def test_multiple_tables(self):
        """Should list multiple tables in order."""
        from app.db.schema import build_schema_light

        tables = [
            TableInfo(name="alpha", columns=[ColumnInfo(name="id", data_type="INT")]),
            TableInfo(name="beta", columns=[ColumnInfo(name="val", data_type="TEXT")]),
        ]

        result = build_schema_light(tables)
        assert "alpha" in result
        assert "beta" in result

    def test_tables_with_no_columns(self):
        """Should handle tables that have no columns."""
        from app.db.schema import build_schema_light

        tables = [
            TableInfo(name="empty", columns=[]),
        ]

        result = build_schema_light(tables)
        assert "empty()" in result


class TestLoadDynamicDescriptions:
    """Tests for _load_dynamic_descriptions (the helper used by both prompt builders)."""

    def test_returns_empty_dict_when_no_db_id(self):
        """Should return an empty dict when db_id is None."""
        from app.db.schema import _load_dynamic_descriptions

        result = _load_dynamic_descriptions(db_id=None)
        assert result == {}

    def test_returns_empty_dict_on_exception(self):
        """Should return an empty dict when load_full_schema raises an exception."""
        from app.db.schema import _load_dynamic_descriptions

        with mock.patch("app.db.schema.load_full_schema", side_effect=Exception("DB error")):
            result = _load_dynamic_descriptions(db_id="db-1")

        assert result == {}

    def test_returns_descriptions_from_persistence(self):
        """Should load and structure descriptions from persistence."""
        from app.db.schema import _load_dynamic_descriptions

        fake_tables = [
            {
                "table_name": "users",
                "description": "用户表",
                "description_en": "Users table",
                "columns": [
                    {"column_name": "id", "description": "ID", "description_en": "Identifier"},
                    {"column_name": "name", "description": "", "description_en": ""},
                ],
            },
        ]

        with mock.patch("app.db.schema.load_full_schema", return_value=fake_tables):
            result = _load_dynamic_descriptions(db_id="db-1")

        assert "users" in result
        assert result["users"]["description"] == "用户表"
        assert result["users"]["description_en"] == "Users table"
        assert result["users"]["columns"]["id"] == "ID"
        assert result["users"]["columns_en"]["id"] == "Identifier"
        # name has no descriptions, so it should not appear
        assert "name" not in result["users"]["columns"]
