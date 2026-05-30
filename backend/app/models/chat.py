from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    db_id: str | None = None
    mode: str = "fast"  # "fast" | "quality"


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tool_calls: list = []
    sql_queries: list[str] = []


# (intentionally left blank — SchemaInfo was unused and removed)
