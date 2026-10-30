"""NOVA — Analytics Service."""

from __future__ import annotations

from sqlalchemy import func, select

from app.database.database import get_db_session
from app.database.models import Conversation, Message, ToolExecution
from app.schemas.analytics import AnalyticsOverview


async def get_analytics(user_id: str | None = None) -> AnalyticsOverview:
    """Compute analytics overview from database."""
    async with get_db_session() as session:
        # Total conversations
        conv_q = select(func.count(Conversation.id))
        if user_id:
            conv_q = conv_q.where(Conversation.user_id == user_id)
        result = await session.execute(conv_q)
        total_conversations = result.scalar() or 0

        # Total messages
        msg_q = select(func.count(Message.id))
        if user_id:
            msg_q = msg_q.where(Message.user_id == user_id)
        result = await session.execute(msg_q)
        total_messages = result.scalar() or 0

        # Voice requests
        voice_q = select(func.count(Message.id)).where(Message.is_voice.is_(True))
        if user_id:
            voice_q = voice_q.where(Message.user_id == user_id)
        result = await session.execute(voice_q)
        voice_requests = result.scalar() or 0

        # Average latencies
        lat_q = select(func.avg(Message.latency_ms)).where(
            Message.role == "assistant", Message.latency_ms.isnot(None)
        )
        if user_id:
            lat_q = lat_q.where(Message.user_id == user_id)
        result = await session.execute(lat_q)
        avg_latency = result.scalar() or 0

        stt_q = select(func.avg(Message.stt_duration_ms)).where(Message.stt_duration_ms.isnot(None))
        if user_id:
            stt_q = stt_q.where(Message.user_id == user_id)
        result = await session.execute(stt_q)
        avg_stt = result.scalar() or 0

        llm_q = select(func.avg(Message.llm_duration_ms)).where(Message.llm_duration_ms.isnot(None))
        if user_id:
            llm_q = llm_q.where(Message.user_id == user_id)
        result = await session.execute(llm_q)
        avg_llm = result.scalar() or 0

        tts_q = select(func.avg(Message.tts_duration_ms)).where(Message.tts_duration_ms.isnot(None))
        if user_id:
            tts_q = tts_q.where(Message.user_id == user_id)
        result = await session.execute(tts_q)
        avg_tts = result.scalar() or 0

        # Tool executions
        tool_q = select(func.count(ToolExecution.id))
        if user_id:
            tool_q = tool_q.where(ToolExecution.user_id == user_id)
        result = await session.execute(tool_q)
        tool_execs = result.scalar() or 0

        # RAG searches (tool executions with document_search)
        rag_q = select(func.count(ToolExecution.id)).where(ToolExecution.tool_name == "document_search")
        if user_id:
            rag_q = rag_q.where(ToolExecution.user_id == user_id)
        result = await session.execute(rag_q)
        rag_searches = result.scalar() or 0

        # Errors
        err_q = select(func.count(ToolExecution.id)).where(ToolExecution.success.is_(False))
        if user_id:
            err_q = err_q.where(ToolExecution.user_id == user_id)
        result = await session.execute(err_q)
        total_errors = result.scalar() or 0

        # Intent distribution
        intent_q = (
            select(Message.intent, func.count(Message.id))
            .where(Message.intent.isnot(None))
        )
        if user_id:
            intent_q = intent_q.where(Message.user_id == user_id)
        result = await session.execute(intent_q.group_by(Message.intent))
        intent_dist = {row[0]: row[1] for row in result.all()}

        # Tool usage
        tool_use_q = select(ToolExecution.tool_name, func.count(ToolExecution.id))
        if user_id:
            tool_use_q = tool_use_q.where(ToolExecution.user_id == user_id)
        result = await session.execute(tool_use_q.group_by(ToolExecution.tool_name))
        tool_usage = {row[0]: row[1] for row in result.all()}

        # Messages per day (last 30 days)
        day_q = select(
            func.date(Message.created_at).label("day"),
            func.count(Message.id).label("count"),
        )
        if user_id:
            day_q = day_q.where(Message.user_id == user_id)
        day_q = (
            day_q.group_by(func.date(Message.created_at))
            .order_by(func.date(Message.created_at).desc())
            .limit(30)
        )
        result = await session.execute(day_q)
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
