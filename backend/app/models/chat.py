from pydantic import BaseModel, Field


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
    tool_calls: list = Field(default_factory=list)
    sql_queries: list[str] = Field(default_factory=list)
    query_results: list[dict] = Field(default_factory=list)


# (intentionally left blank — SchemaInfo was unused and removed)
