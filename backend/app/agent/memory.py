"""NOVA — Memory System (Short-term + Long-term)."""

from __future__ import annotations

from app.database.database import get_db_session
from app.database.repositories import MemoryRepo


async def store_memory(content: str, category: str = "general", source: str = "user") -> str:
    """Store a long-term memory. Returns the memory ID."""
    async with get_db_session() as session:
        mem = await MemoryRepo.create(session, content=content, category=category, source=source)
        return mem.id


async def search_memories(query: str) -> list[dict]:
    """Search long-term memories."""
    async with get_db_session() as session:
        memories = await MemoryRepo.search(session, query)
        return [
            {
                "id": m.id,
                "content": m.content,
                "category": m.category,
                "source": m.source or "user",
                "created_at": str(m.created_at),
            }
            for m in memories
        ]


async def list_memories() -> list[dict]:
    """List all long-term memories."""
    async with get_db_session() as session:
        memories = await MemoryRepo.list_all(session)
        return [
            {
                "id": m.id,
                "content": m.content,
                "category": m.category,
                "source": m.source or "user",
                "created_at": str(m.created_at),
            }
            for m in memories
        ]


async def delete_memory(memory_id: str) -> bool:
    """Delete a specific memory."""
    async with get_db_session() as session:
        return await MemoryRepo.delete(session, memory_id)
