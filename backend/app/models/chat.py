from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Incoming chat request."""

    message: str
    session_id: str | None = None
    db_id: str | None = None
    mode: str = "fast"  # "fast" | "quality"


class ChatResponse(BaseModel):
    """Chat response returned by the backend."""

    reply: str
    session_id: str
    tool_calls: list = []
    sql_queries: list[str] = []
    query_results: list[dict] = []


# (intentionally left blank — SchemaInfo was unused and removed)
