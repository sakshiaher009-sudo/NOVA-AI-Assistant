"""NOVA — Conversation Routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.database.database import get_db_session
from app.database.repositories import ConversationRepo, MessageRepo
from app.schemas.chat import ConversationSummary, ConversationDetail, ConversationCreate, MessageOut

router = APIRouter(tags=["conversations"])


@router.get("/api/conversations", response_model=list[ConversationSummary])
async def list_conversations():
    """List all conversations."""
    async with get_db_session() as session:
        convs = await ConversationRepo.list_all(session)
        result = []
        for c in convs:
            msgs = await MessageRepo.get_by_conversation(session, c.id)
            result.append(ConversationSummary(
                id=c.id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
                message_count=len(msgs),
            ))
        return result


@router.post("/api/conversations", response_model=ConversationSummary)
async def create_conversation(request: ConversationCreate):
    """Create a new conversation."""
    async with get_db_session() as session:
        conv = await ConversationRepo.create(session, title=request.title)
        return ConversationSummary(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=0,
        )


@router.get("/api/conversations/{conv_id}", response_model=ConversationDetail)
async def get_conversation(conv_id: str):
    """Get a conversation with messages."""
    async with get_db_session() as session:
        conv = await ConversationRepo.get(session, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        msgs = await MessageRepo.get_by_conversation(session, conv_id)
        return ConversationDetail(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            messages=[
                MessageOut(
                    id=m.id, role=m.role, content=m.content,
                    intent=m.intent, confidence=m.confidence,
                    tool_name=m.tool_name, is_voice=m.is_voice,
                    latency_ms=m.latency_ms, created_at=m.created_at,
                )
                for m in msgs
            ],
        )


@router.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """Delete a conversation."""
    async with get_db_session() as session:
        deleted = await ConversationRepo.delete(session, conv_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"status": "deleted"}
