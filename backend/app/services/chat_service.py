import json
from collections.abc import AsyncGenerator

from app.agent.orchestrator import process_message, process_message_stream
from app.schemas.chat import ChatRequest, ChatResponse


async def handle_chat(request: ChatRequest, user_id: str = "default_user") -> ChatResponse:
    """Process a text chat message through the agent pipeline with user ownership."""
    return await process_message(
        message=request.message,
        conversation_id=request.conversation_id,
        is_voice=False,
        user_id=user_id,
    )


async def handle_chat_stream(
    request: ChatRequest, user_id: str = "default_user"
) -> AsyncGenerator[str, None]:
    """Process a text chat message and stream Server-Sent Events with user ownership."""
    async for event in process_message_stream(
        message=request.message,
        conversation_id=request.conversation_id,
        is_voice=False,
        user_id=user_id,
    ):
        yield f"data: {json.dumps(event)}\n\n"
