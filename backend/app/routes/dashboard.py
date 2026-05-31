"""Dashboard routes — list, create, delete dashboard items for current user."""

from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import state
from ..auth.middleware import get_current_user

router = APIRouter()


class DashboardItemCreate(BaseModel):
    """Request body for creating a new dashboard item."""
    title: str = ""
    query: str | None = None
    chart_type: str = "table"
    chart_data: str | None = None


@router.get("/api/dashboard/items")
async def list_dashboard_items(current_user: dict = Depends(get_current_user)):
    """Return all dashboard items belonging to the current user, ordered by creation time descending."""
    if state._sqlite is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    rows = state._sqlite.execute(
        "SELECT id, user_id, title, query, chart_type, chart_data, created_at "
        "FROM dashboard_items WHERE user_id = ? ORDER BY created_at DESC",
        (current_user["id"],),
    ).fetchall()
    return {
        "items": [
            {
                "id": row[0],
                "user_id": row[1],
                "title": row[2],
                "query": row[3],
                "chart_type": row[4],
                "chart_data": json.loads(row[5]) if row[5] else None,
                "created_at": row[6],
            }
            for row in rows
        ]
    }


@router.post("/api/dashboard/items", status_code=201)
async def create_dashboard_item(
    body: DashboardItemCreate,
    current_user: dict = Depends(get_current_user),
):
    """Add a new dashboard item for the current user and return the created item."""
    if state._sqlite is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    item_id = str(uuid.uuid4())
    now = time.time()
    chart_data_str = json.dumps(body.chart_data, ensure_ascii=False) if body.chart_data else None
    state._sqlite.execute(
        "INSERT INTO dashboard_items (id, user_id, title, query, chart_type, chart_data, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (item_id, current_user["id"], body.title, body.query, body.chart_type, chart_data_str, now),
    )
    state._sqlite.commit()
    return {
        "id": item_id,
        "user_id": current_user["id"],
        "title": body.title,
        "query": body.query,
        "chart_type": body.chart_type,
        "chart_data": body.chart_data,
        "created_at": now,
    }


@router.delete("/api/dashboard/items/{item_id}")
async def delete_dashboard_item(
    item_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a dashboard item by id, ensuring it belongs to the current user."""
    if state._sqlite is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    row = state._sqlite.execute(
        "SELECT id FROM dashboard_items WHERE id = ? AND user_id = ?",
        (item_id, current_user["id"]),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Dashboard item not found")
    state._sqlite.execute("DELETE FROM dashboard_items WHERE id = ?", (item_id,))
    state._sqlite.commit()
    return {"ok": True}
