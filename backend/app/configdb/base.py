from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .. import state

logger = logging.getLogger("shuyu.main")


def create_configdb_engine(configdb_url: str) -> tuple:
    """Create SQLAlchemy engine and session factory from a connection URL.

    Args:
        configdb_url: SQLAlchemy connection URL.
                      e.g. ``sqlite:///path/to/config.db``
                      or ``mysql+pymysql://user:pass@host:port/db``

    Returns:
        Tuple of ``(engine, session_factory)``.
    """
    engine = create_engine(
        configdb_url,
        pool_pre_ping=True,
        # SQLite-specific: allow multi-thread access
        connect_args={"check_same_thread": False} if configdb_url.startswith("sqlite") else {},
    )
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, SessionLocal


def get_session() -> Session:
    """Get a new ConfigDB session. Caller must close it."""
    if state._configdb_session_factory is None:
        raise RuntimeError("ConfigDB not initialized")
    return state._configdb_session_factory()


@contextmanager
def scoped_session() -> Iterator[Session]:
    """Context manager that provides a session and commits/closes on exit.

    Usage::

        with scoped_session() as session:
            user = session.query(User).first()
            # auto-committed on success
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
