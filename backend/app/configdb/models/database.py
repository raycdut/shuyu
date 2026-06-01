from __future__ import annotations

from sqlalchemy import Column, String, Integer, Text

from . import Base


class DatabaseConnection(Base):
    __tablename__ = "databases"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False, default="duckdb")
    path = Column(Text, nullable=True)
    connection_string = Column(Text, nullable=True)
    host = Column(String(255), nullable=True)
    port = Column(Integer, nullable=True)
    username = Column(String(255), nullable=True)
    password = Column(Text, nullable=True)
    db_name = Column(String(255), nullable=True)
    include_tables = Column(Text, nullable=True)
    exclude_tables = Column(Text, nullable=True)
    is_active = Column(Integer, default=0, nullable=False)
    schema_status = Column(String(50), default="pending", nullable=True)
