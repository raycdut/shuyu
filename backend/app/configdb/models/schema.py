from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from . import Base


class ImportedTable(Base):
    __tablename__ = "imported_tables"

    id = Column(String(36), primary_key=True)
    database_id = Column(String(36), ForeignKey("databases.id"), nullable=False)
    table_name = Column(String(255), nullable=False)
    table_type = Column(String(50), default="TABLE")
    row_count = Column(Integer, nullable=True)
    description = Column(Text, default="", nullable=True)
    description_en = Column(Text, default="", nullable=True)
    raw_ddl = Column(Text, nullable=True)
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)

    columns = relationship("ImportedColumn", back_populates="table", cascade="all, delete-orphan",
                           order_by="ImportedColumn.ordinal_position")


class ImportedColumn(Base):
    __tablename__ = "imported_columns"

    id = Column(String(36), primary_key=True)
    table_id = Column(String(36), ForeignKey("imported_tables.id"), nullable=False)
    column_name = Column(String(255), nullable=False)
    data_type = Column(String(100), nullable=False)
    is_nullable = Column(Integer, default=1)
    is_primary_key = Column(Integer, default=0)
    default_value = Column(Text, nullable=True)
    ordinal_position = Column(Integer, nullable=True)
    description = Column(Text, default="", nullable=True)
    description_en = Column(Text, default="", nullable=True)
    sample_values = Column(Text, nullable=True)
    created_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)

    table = relationship("ImportedTable", back_populates="columns")
