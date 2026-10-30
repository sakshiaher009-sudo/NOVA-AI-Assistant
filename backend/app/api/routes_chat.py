"""NOVA — Chat Routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.dependencies.auth import get_current_user_id
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import handle_chat, handle_chat_stream

router = APIRouter(tags=["chat"])


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Process a text chat message with user authentication."""
    try:
        return await handle_chat(request, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@router.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Process a text chat message with Server-Sent Events (SSE) token streaming."""
    try:
        return StreamingResponse(
            handle_chat_stream(request, user_id=user_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming failed: {str(e)}")
