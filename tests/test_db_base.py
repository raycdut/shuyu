"""Tests for db/base.py — TableInfo, ColumnInfo, QueryResult."""

from __future__ import annotations

from app.db.base import ColumnInfo, QueryResult, TableInfo


class TestColumnInfo:
    def test_defaults(self):
        c = ColumnInfo(name="id", data_type="INTEGER")
        assert c.name == "id"
        assert c.data_type == "INTEGER"
        assert c.is_nullable is True
        assert c.is_primary_key is False
        assert c.comment == ""

    def test_primary_key(self):
        c = ColumnInfo(name="id", data_type="INTEGER", is_primary_key=True)
        assert c.is_primary_key is True


class TestTableInfo:
    def test_to_prompt_block_no_columns(self):
        t = TableInfo(name="users")
        block = t.to_prompt_block()
        assert "表: users" in block

    def test_to_prompt_block_with_columns(self):
        cols = [
            ColumnInfo(name="id", data_type="INTEGER", is_primary_key=True),
            ColumnInfo(name="name", data_type="VARCHAR", comment="用户姓名"),
        ]
        t = TableInfo(name="users", columns=cols)
        block = t.to_prompt_block()
        assert "表: users" in block
        assert "id: INTEGER" in block
        assert "(PK)" in block
        assert "name: VARCHAR" in block
        assert "用户姓名" in block


class TestQueryResult:
    def test_empty(self):
        qr = QueryResult(columns=[], rows=[])
        assert qr.row_count == 0
        assert qr.to_text() == "(empty result set)"

    def test_to_text_simple(self):
        qr = QueryResult(columns=["name", "age"], rows=[["Alice", 30], ["Bob", 25]])
        text = qr.to_text()
        assert "name | age" in text
        assert "Alice | 30" in text
        assert "Bob | 25" in text

    def test_to_text_with_nulls(self):
        qr = QueryResult(columns=["a", "b"], rows=[[None, "x"]])
        text = qr.to_text()
        assert "NULL | x" in text

    def test_to_text_truncated(self):
        rows = [[f"row{i}"] for i in range(25)]
        qr = QueryResult(columns=["col"], rows=rows, row_count=100)
        text = qr.to_text(max_rows=20)
        assert "... (80 more rows)" in text
        assert text.count("row") == 21  # 20 rows + 1 from "rows" in truncation msg

    def test_to_html(self):
        qr = QueryResult(columns=["name"], rows=[["Alice"], ["Bob"]])
        html = qr.to_html()
        assert "<table" in html
        assert "<th>name</th>" in html
        assert "Alice" in html
        assert "Bob" in html

    def test_to_html_truncated(self):
        rows = [[f"row{i}"] for i in range(250)]
        qr = QueryResult(columns=["col"], rows=rows, row_count=500)
        html = qr.to_html(max_rows=200)
        assert "仅显示前 200 行" in html

    def test_row_count_manual(self):
        qr = QueryResult(columns=["x"], rows=[["a"]], row_count=999)
        assert qr.row_count == 999
