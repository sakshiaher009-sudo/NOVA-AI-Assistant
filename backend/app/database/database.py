"""NOVA — Async SQLite Database Engine & Session Management."""

from __future__ import annotations

from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator

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
    """Resolve the database URL, ensuring the data directory exists."""
    settings = get_settings()
    url = settings.database_url
    # Ensure data directory exists for SQLite
    if "sqlite" in url:
        # Extract path from URL like sqlite+aiosqlite:///./data/app.db
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
        _engine = create_async_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
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
