"""Schema route — GET /api/schema"""

from __future__ import annotations

from fastapi import APIRouter

from .. import state

router = APIRouter()


@router.get("/api/schema")
async def get_schema():
    """Return database schema — now use GET /api/database/{id}/tables per DB."""
    return {"tables": [], "note": "Please select a database and use GET /api/database/{id}/tables"}
