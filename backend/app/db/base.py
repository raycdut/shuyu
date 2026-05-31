"""Abstract database connector interface."""

from __future__ import annotations

import html as _html
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    comment: str = ""


@dataclass
class TableInfo:
    name: str
    schema: str = "public"
    columns: list[ColumnInfo] = None

    def to_prompt_block(self) -> str:
        """Format table info for LLM system prompt."""
        cols = "\n    ".join(
            f"- {c.name}: {c.data_type}"
            + (" (PK)" if c.is_primary_key else "")
            + (f" — {c.comment}" if c.comment else "")
            for c in (self.columns or [])
        )
        return f"""表: {self.name}
  {cols}"""


class QueryResult:
    def __init__(self, columns: list[str], rows: list[list[Any]], row_count: int = None):
        self.columns = columns
        self.rows = rows
        self.row_count = row_count if row_count is not None else len(rows)

    def to_text(self, max_rows: int = 20) -> str:
        """Format for LLM consumption (truncated)."""
        if self.row_count == 0:
            return "(empty result set)"

        lines = []
        header = " | ".join(self.columns)
        lines.append(header)
        lines.append("-" * len(header))

        for row in self.rows[:max_rows]:
            lines.append(" | ".join(str(v) if v is not None else "NULL" for v in row))

        if self.row_count > max_rows:
            lines.append(f"... ({self.row_count - max_rows} more rows)")

        return "\n".join(lines)

    def to_html(self, max_rows: int = 200) -> str:
        """Format as HTML table for UI."""
        rows_display = self.rows[:max_rows]
        html = '<table class="query-results">\n<thead><tr>'
        for col in self.columns:
            html += f"<th>{col}</th>"
        html += "</tr></thead>\n<tbody>\n"
        for row in rows_display:
            html += "<tr>"
            for val in row:
                html += f"<td>{_html.escape(str(val)) if val is not None else ''}</td>"
            html += "</tr>\n"
        html += "</tbody></table>\n"
        if self.row_count > max_rows:
            html += f'<p class="truncated">... 仅显示前 {max_rows} 行，共 {self.row_count} 行</p>\n'
        return html


class DatabaseConnector(ABC):
    """Abstract interface for all database connectors."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the database."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection."""
        ...

    @abstractmethod
    def get_schema(self) -> list[TableInfo]:
        """Discover and return all accessible tables and columns."""
        ...

    @abstractmethod
    def execute(self, sql: str, max_rows: int = 1000) -> QueryResult:
        """Execute a SQL query and return results."""
        ...

    @abstractmethod
    def test_connection(self) -> bool:
        """Verify the connection works."""
        ...
