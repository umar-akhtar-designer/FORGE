"""SQLAlchemy engine + session helpers (thread-safe for background missions)."""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from . import config
from .orm import Base

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        kwargs = {"connect_args": {"check_same_thread": False}} if config.DB_URL.startswith("sqlite") else {}
        _engine = create_engine(config.DB_URL, **kwargs)
    return _engine


def get_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)
    return _session_factory


def init_db() -> None:
    config.ensure_dirs()
    Base.metadata.create_all(get_engine())


@contextmanager
def session_scope() -> Session:
    session = get_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()