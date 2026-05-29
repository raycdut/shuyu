from pydantic import BaseModel


class SessionRenameRequest(BaseModel):
    title: str


class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: list[dict]
