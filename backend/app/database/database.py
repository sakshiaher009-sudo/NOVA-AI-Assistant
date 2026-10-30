"""NOVA — Async Database Engine & Session Management.

Supports SQLite (via aiosqlite for local dev and tests) and PostgreSQL
(via asyncpg for Supabase and production deployments).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.database.models import Base

_engine = None
_session_factory = None


def _resolve_db_url() -> str:
    """Resolve the database URL, ensuring dialect compatibility and SQLite paths."""
    settings = get_settings()
    url = settings.database_url.strip()

    # Normalize standard postgresql URLs to use the asyncpg async driver
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Ensure data directory exists for SQLite
    if "sqlite" in url:
        db_path_str = url.split("///")[-1]
        db_path = Path(db_path_str)
        if not db_path.is_absolute():
            db_path = settings.project_root / db_path_str
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{db_path}"
    return url


async def get_engine():
    """Return the shared async engine, creating it if needed."""
    global _engine
    if _engine is None:
        url = _resolve_db_url()
        connect_args = {}
        # Apply SQLite-specific arguments only when SQLite dialect is selected
        if "sqlite" in url:
            connect_args["check_same_thread"] = False

        _engine = create_async_engine(
            url,
            echo=False,
            connect_args=connect_args,
        )
        if "sqlite" in url:
            @event.listens_for(_engine.sync_engine, "connect")
            def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
    return _engine


async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared session factory."""
    global _session_factory
    if _session_factory is None:
        engine = await get_engine()
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


async def init_db() -> None:
    """Create all tables if they don't exist."""
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose the engine."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session with automatic commit/rollback."""
    factory = await get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
