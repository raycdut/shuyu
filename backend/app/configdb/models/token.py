from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float, Text

from . import Base


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(100), nullable=False)
    prompt = Column(Integer, default=0, nullable=False)
    completion = Column(Integer, default=0, nullable=False)
    total = Column(Integer, default=0, nullable=False)
    session_id = Column(String(36), nullable=True)
    created_at = Column(Float, nullable=False)
