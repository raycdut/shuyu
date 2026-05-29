"""Session routes — list, get messages, rename, delete"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import state
from ..models.session import SessionMessagesResponse, SessionRenameRequest

router = APIRouter()


@router.get("/api/sessions")
async def list_sessions():
    """List active sessions."""
    if state.session_manager is None:
        return {"sessions": []}
    return {
        "sessions": [
            {
                "id": s.session_id,
                "title": s.metadata.get("title", "新对话"),
                "messages": len(s.messages),
                "last_active": s.last_active,
            }
            for s in state.session_manager._sessions.values()
        ]
    }


@router.get("/api/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_session_messages(session_id: str):
    """Get messages for a specific session."""
    if state.session_manager is None:
        raise HTTPException(503, "Session manager not initialized")
    session = state.session_manager.get_or_create(session_id)
    return SessionMessagesResponse(
        session_id=session_id,
        messages=session.get_messages(),
    )


@router.patch("/api/sessions/{session_id}")
async def rename_session(session_id: str, req: SessionRenameRequest):
    """Rename a session."""
    if state.session_manager is None:
        raise HTTPException(503, "Session manager not initialized")
    state.session_manager.rename(session_id, req.title)
    return {"ok": True}


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if state.session_manager is None:
        raise HTTPException(503, "Session manager not initialized")
    state.session_manager.delete(session_id)
    return {"ok": True}
