from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, func, CheckConstraint

from . import Base


class SystemConfig(Base):
    __tablename__ = "system_config"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_system_config_single_row"),
    )

    id = Column(Integer, primary_key=True, autoincrement=False)
    config = Column(Text, default="{}", nullable=False)
    updated_at = Column(String(50), nullable=False)
    updated_by = Column(String(255), nullable=True)


class UserConfig(Base):
    __tablename__ = "user_configs"

    user_id = Column(String(36), primary_key=True)
    config = Column(Text, default="{}", nullable=False)
    updated_at = Column(String(50), nullable=False)


class ConfigChangelog(Base):
    __tablename__ = "config_changelog"
    __table_args__ = (
        CheckConstraint(
            "config_type IN ('system', 'user', 'user_mgmt', 'database')",
            name="ck_config_changelog_type",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_type = Column(String(50), nullable=False)
    user_id = Column(String(36), nullable=True)
    changed_by = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    diff = Column(Text, nullable=True)
    created_at = Column(String(50), nullable=False)


class LlmProvider(Base):
    __tablename__ = "llm_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False, default="openai")
    model = Column(String(100), nullable=False, default="gpt-4o")
    api_key = Column(Text, default="", nullable=True)
    api_base = Column(Text, default="", nullable=True)
    timeout = Column(Integer, default=120, nullable=True)
    is_active = Column(Integer, default=0, nullable=False)
    created_at = Column(Float, nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=False)
