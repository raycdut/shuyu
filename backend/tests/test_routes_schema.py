"""Tests for schema route — GET /api/schema."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create a FastAPI TestClient."""
    return TestClient(app)


class TestSchema:
    """Tests for GET /api/schema."""

    def test_get_schema(self, client):
        """Should return a placeholder response with empty tables and a note."""
        resp = client.get("/api/schema")
        assert resp.status_code == 200
        data = resp.json()
        assert "tables" in data
        assert "note" in data
        assert data["tables"] == []
        assert "database" in data["note"]
