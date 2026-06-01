from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import relationship

from . import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)
    title = Column(String(255), default="", nullable=False)
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan",
                            order_by="Message.id")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, default="", nullable=False)
    tool_data = Column(Text, nullable=True)
    created_at = Column(Float, nullable=False)

    session = relationship("Session", back_populates="messages")
