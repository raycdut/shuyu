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
    messages = session.get_messages()

    # Attach persisted query_results to the last assistant message
    query_results = session.metadata.get("_query_results")
    if query_results and messages:
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "assistant":
                messages[i] = {**messages[i], "query_results": query_results}
                break

    return SessionMessagesResponse(
        session_id=session_id,
        messages=messages,
    )


@router.patch("/api/sessions/{session_id}")
async def rename_session(session_id: str, req: SessionRenameRequest):
    """Rename a session."""
    if state.session_manager is None:
        raise HTTPException(503, "Session manager not initialized")
    state.session_manager.rename(session_id, req.title)
    return {"ok": True}


@router.post("/api/sessions/clear")
async def clear_all_sessions():
    """Delete ALL sessions."""
    if state.session_manager is None:
        raise HTTPException(503, "Session manager not initialized")
    count = state.session_manager.clear_all()
    return {"ok": True, "deleted": count}


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a single session."""
    if state.session_manager is None:
        raise HTTPException(503, "Session manager not initialized")
    state.session_manager.delete(session_id)
    return {"ok": True}
