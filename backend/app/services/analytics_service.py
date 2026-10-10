"""NOVA — Analytics Service."""

from __future__ import annotations

from sqlalchemy import select, func, case, distinct

from app.database.database import get_db_session
from app.database.models import Conversation, Message, ToolExecution, SystemEvent
from app.schemas.analytics import AnalyticsOverview


async def get_analytics() -> AnalyticsOverview:
    """Compute analytics overview from database."""
    async with get_db_session() as session:
        # Total conversations
        result = await session.execute(select(func.count(Conversation.id)))
        total_conversations = result.scalar() or 0

        # Total messages
        result = await session.execute(select(func.count(Message.id)))
        total_messages = result.scalar() or 0

        # Voice requests
        result = await session.execute(
            select(func.count(Message.id)).where(Message.is_voice == True)
        )
        voice_requests = result.scalar() or 0

        # Average latencies
        result = await session.execute(
            select(func.avg(Message.latency_ms)).where(
                Message.role == "assistant", Message.latency_ms.isnot(None)
            )
        )
        avg_latency = result.scalar() or 0

        result = await session.execute(
            select(func.avg(Message.stt_duration_ms)).where(Message.stt_duration_ms.isnot(None))
        )
        avg_stt = result.scalar() or 0

        result = await session.execute(
            select(func.avg(Message.llm_duration_ms)).where(Message.llm_duration_ms.isnot(None))
        )
        avg_llm = result.scalar() or 0

        result = await session.execute(
            select(func.avg(Message.tts_duration_ms)).where(Message.tts_duration_ms.isnot(None))
        )
        avg_tts = result.scalar() or 0

        # Tool executions
        result = await session.execute(select(func.count(ToolExecution.id)))
        tool_execs = result.scalar() or 0

        # RAG searches (tool executions with document_search)
        result = await session.execute(
            select(func.count(ToolExecution.id)).where(ToolExecution.tool_name == "document_search")
        )
        rag_searches = result.scalar() or 0

        # Errors
        result = await session.execute(
            select(func.count(ToolExecution.id)).where(ToolExecution.success == False)
        )
        total_errors = result.scalar() or 0

        # Intent distribution
        result = await session.execute(
            select(Message.intent, func.count(Message.id))
            .where(Message.intent.isnot(None))
            .group_by(Message.intent)
        )
        intent_dist = {row[0]: row[1] for row in result.all()}

        # Tool usage
        result = await session.execute(
            select(ToolExecution.tool_name, func.count(ToolExecution.id))
            .group_by(ToolExecution.tool_name)
        )
        tool_usage = {row[0]: row[1] for row in result.all()}

        # Messages per day (last 30 days)
        result = await session.execute(
            select(
                func.date(Message.created_at).label("day"),
                func.count(Message.id).label("count"),
            )
            .group_by(func.date(Message.created_at))
            .order_by(func.date(Message.created_at).desc())
            .limit(30)
        )
        messages_per_day = [{"date": str(row[0]), "count": row[1]} for row in result.all()]

    return AnalyticsOverview(
        total_conversations=total_conversations,
        total_messages=total_messages,
        voice_requests=voice_requests,
        avg_response_latency_ms=round(avg_latency, 1),
        avg_stt_duration_ms=round(avg_stt, 1),
        avg_llm_duration_ms=round(avg_llm, 1),
        avg_tts_duration_ms=round(avg_tts, 1),
        rag_searches=rag_searches,
        tool_executions=tool_execs,
        total_errors=total_errors,
        intent_distribution=intent_dist,
        tool_usage=tool_usage,
        messages_per_day=messages_per_day,
    )
