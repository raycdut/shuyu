from __future__ import annotations

from sqlalchemy import Column, String, Boolean, Integer, Text
from sqlalchemy.orm import relationship

from . import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")
    is_active = Column(Integer, default=1, nullable=False)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)
    last_login_at = Column(String(50), nullable=True)


class UserDatabase(Base):
    __tablename__ = "user_databases"

    user_id = Column(String(36), primary_key=True)
    database_id = Column(String(36), primary_key=True)
