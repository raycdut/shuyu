from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    db_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tool_calls: list = []
    sql_queries: list[str] = []


class SchemaInfo(BaseModel):
    tables: list[dict]
