"""NOVA — Conversation Routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.database.database import get_db_session
from app.database.repositories import ConversationRepo, MessageRepo
from app.dependencies.auth import get_current_user_id
from app.schemas.chat import ConversationCreate, ConversationDetail, ConversationSummary, MessageOut

router = APIRouter(tags=["conversations"])


@router.get("/api/conversations", response_model=list[ConversationSummary])
async def list_conversations(user_id: str = Depends(get_current_user_id)):
    """List all conversations for the authenticated user."""
    async with get_db_session() as session:
        convs = await ConversationRepo.list_all(session, user_id=user_id)
        result = []
        for c in convs:
            msgs = await MessageRepo.get_by_conversation(session, c.id, user_id=user_id)
            result.append(ConversationSummary(
                id=c.id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
                message_count=len(msgs),
            ))
        return result


@router.post("/api/conversations", response_model=ConversationSummary)
async def create_conversation(
    request: ConversationCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new conversation owned by the authenticated user."""
    async with get_db_session() as session:
        conv = await ConversationRepo.create(session, title=request.title, user_id=user_id)
        return ConversationSummary(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=0,
        )


@router.get("/api/conversations/{conv_id}", response_model=ConversationDetail)
async def get_conversation(
    conv_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get a conversation with messages after verifying ownership."""
    async with get_db_session() as session:
        conv = await ConversationRepo.get(session, conv_id, user_id=user_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        msgs = await MessageRepo.get_by_conversation(session, conv_id, user_id=user_id)
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
async def delete_conversation(
    conv_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a conversation after verifying ownership."""
    async with get_db_session() as session:
        deleted = await ConversationRepo.delete(session, conv_id, user_id=user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"status": "deleted"}
