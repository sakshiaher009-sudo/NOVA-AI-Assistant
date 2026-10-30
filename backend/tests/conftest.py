"""Shared isolated database lifecycle for backend tests."""

import pytest_asyncio

from app.database.database import close_db, init_db


@pytest_asyncio.fixture(autouse=True)
async def isolated_database_schema():
    """Create schema in the test-only database selected by DATABASE_URL."""
    await init_db()
    yield
    await close_db()
