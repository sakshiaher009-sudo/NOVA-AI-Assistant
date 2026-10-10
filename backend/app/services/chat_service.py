from typing import AsyncGenerator
import json

from app.agent.orchestrator import process_message, process_message_stream
from app.schemas.chat import ChatRequest, ChatResponse


async def handle_chat(request: ChatRequest) -> ChatResponse:
    """Process a text chat message through the agent pipeline."""
    return await process_message(
        message=request.message,
        conversation_id=request.conversation_id,
        is_voice=False,
    )


async def handle_chat_stream(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Process a text chat message and stream Server-Sent Events."""
    async for event in process_message_stream(
        message=request.message,
        conversation_id=request.conversation_id,
        is_voice=False,
    ):
        yield f"data: {json.dumps(event)}\n\n"
