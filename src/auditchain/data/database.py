"""Database connection and session management.

This module exposes the SQLAlchemy engine and a session factory.
All database access in the project goes through here — never create
connections elsewhere.

We use SQLAlchemy 2.0 style with synchronous sessions for simplicity.
For high-throughput scenarios (many concurrent agent runs) we can
swap to async sessions later without changing the repository layer.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models.

    Every table in our schema inherits from this. SQLAlchemy uses it
    to track metadata and generate SQL.
    """


def _build_engine() -> Engine:
    """Create the SQLAlchemy engine with sensible defaults."""
    settings = get_settings()
    engine = create_engine(
        settings.sync_database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    logger.info("database_engine_created", url_host=settings.postgres_host)
    return engine


engine: Engine = _build_engine()

SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a database session that auto-commits on success and rolls back on error.

    Usage:
        with get_session() as session:
            session.add(some_object)
            # commit happens automatically when block exits cleanly
    """
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("database_session_rollback")
        raise
    finally:
        session.close()