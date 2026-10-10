"""NOVA — Database Repository Layer (CRUD operations)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from app.database.models import (
    Conversation,
    Document,
    DocumentChunk,
    Memory,
    Message,
    Note,
    Reminder,
    SystemEvent,
    ToolExecution,
    UserSettings,
)


def new_id() -> str:
    """Generate a time-sorted UUID v7."""
    return str(uuid7())


# ── Conversations ──────────────────────────────────────────────

class ConversationRepo:
    @staticmethod
    async def create(session: AsyncSession, title: str = "New Conversation") -> Conversation:
        conv = Conversation(id=new_id(), title=title)
        session.add(conv)
        await session.flush()
        return conv

    @staticmethod
    async def get(session: AsyncSession, conv_id: str) -> Optional[Conversation]:
        result = await session.execute(select(Conversation).where(Conversation.id == conv_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(session: AsyncSession, limit: int = 50) -> list[Conversation]:
        result = await session.execute(
            select(Conversation)
            .where(Conversation.is_archived == False)
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def delete(session: AsyncSession, conv_id: str) -> bool:
        result = await session.execute(delete(Conversation).where(Conversation.id == conv_id))
        return result.rowcount > 0

    @staticmethod
    async def update_title(session: AsyncSession, conv_id: str, title: str) -> None:
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conv_id)
            .values(title=title, updated_at=datetime.utcnow())
        )


# ── Messages ──────────────────────────────────────────────────

class MessageRepo:
    @staticmethod
    async def create(
        session: AsyncSession,
        conversation_id: str,
        role: str,
        content: str,
        *,
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        entities: Optional[dict] = None,
        tool_name: Optional[str] = None,
        tool_result: Optional[dict] = None,
        latency_ms: Optional[int] = None,
        stt_duration_ms: Optional[int] = None,
        llm_duration_ms: Optional[int] = None,
        tts_duration_ms: Optional[int] = None,
        is_voice: bool = False,
    ) -> Message:
        msg = Message(
            id=new_id(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            intent=intent,
            confidence=confidence,
            entities_json=json.dumps(entities) if entities else None,
            tool_name=tool_name,
            tool_result_json=json.dumps(tool_result) if tool_result else None,
            latency_ms=latency_ms,
            stt_duration_ms=stt_duration_ms,
            llm_duration_ms=llm_duration_ms,
            tts_duration_ms=tts_duration_ms,
            is_voice=is_voice,
        )
        session.add(msg)
        await session.flush()
        # Update conversation timestamp
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=datetime.utcnow())
        )
        return msg

    @staticmethod
    async def get_by_conversation(
        session: AsyncSession, conversation_id: str, limit: int = 100
    ) -> list[Message]:
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())


# ── Documents ─────────────────────────────────────────────────

class DocumentRepo:
    @staticmethod
    async def create(
        session: AsyncSession,
        filename: str,
        original_filename: str,
        file_extension: str,
        file_size_bytes: int,
    ) -> Document:
        doc = Document(
            id=new_id(),
            filename=filename,
            original_filename=original_filename,
            file_extension=file_extension,
            file_size_bytes=file_size_bytes,
            status="pending",
        )
        session.add(doc)
        await session.flush()
        return doc

    @staticmethod
    async def get(session: AsyncSession, doc_id: str) -> Optional[Document]:
        result = await session.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(session: AsyncSession) -> list[Document]:
        result = await session.execute(select(Document).order_by(desc(Document.created_at)))
        return list(result.scalars().all())

    @staticmethod
    async def update_status(
        session: AsyncSession,
        doc_id: str,
        status: str,
        chunk_count: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        await session.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(
                status=status,
                chunk_count=chunk_count,
                error_message=error_message,
                updated_at=datetime.utcnow(),
            )
        )

    @staticmethod
    async def delete(session: AsyncSession, doc_id: str) -> bool:
        result = await session.execute(delete(Document).where(Document.id == doc_id))
        return result.rowcount > 0


class ChunkRepo:
    @staticmethod
    async def create_many(
        session: AsyncSession, document_id: str, chunks: list[str]
    ) -> list[DocumentChunk]:
        records = []
        for i, text in enumerate(chunks):
            c = DocumentChunk(
                id=new_id(),
                document_id=document_id,
                chunk_index=i,
                content=text,
                char_count=len(text),
            )
            session.add(c)
            records.append(c)
        await session.flush()
        return records

    @staticmethod
    async def get_by_document(session: AsyncSession, document_id: str) -> list[DocumentChunk]:
        result = await session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.scalars().all())

    @staticmethod
    async def delete_by_document(session: AsyncSession, document_id: str) -> None:
        await session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )


# ── Memory ────────────────────────────────────────────────────

class MemoryRepo:
    @staticmethod
    async def create(
        session: AsyncSession, content: str, category: str = "general", source: str = "user"
    ) -> Memory:
        mem = Memory(id=new_id(), content=content, category=category, source=source)
        session.add(mem)
        await session.flush()
        return mem

    @staticmethod
    async def list_all(session: AsyncSession) -> list[Memory]:
        result = await session.execute(select(Memory).order_by(desc(Memory.created_at)))
        return list(result.scalars().all())

    @staticmethod
    async def delete(session: AsyncSession, mem_id: str) -> bool:
        result = await session.execute(delete(Memory).where(Memory.id == mem_id))
        return result.rowcount > 0

    @staticmethod
    async def search(session: AsyncSession, query: str) -> list[Memory]:
        result = await session.execute(
            select(Memory)
            .where(Memory.content.ilike(f"%{query}%"))
            .order_by(desc(Memory.created_at))
        )
        return list(result.scalars().all())


# ── Notes ─────────────────────────────────────────────────────

class NoteRepo:
    @staticmethod
    async def create(session: AsyncSession, title: str, content: str = "", tags: str = "") -> Note:
        note = Note(id=new_id(), title=title, content=content, tags=tags)
        session.add(note)
        await session.flush()
        return note

    @staticmethod
    async def get(session: AsyncSession, note_id: str) -> Optional[Note]:
        result = await session.execute(select(Note).where(Note.id == note_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(session: AsyncSession) -> list[Note]:
        result = await session.execute(select(Note).order_by(desc(Note.created_at)))
        return list(result.scalars().all())

    @staticmethod
    async def update(
        session: AsyncSession, note_id: str, title: Optional[str] = None, content: Optional[str] = None, tags: Optional[str] = None
    ) -> bool:
        values: dict = {"updated_at": datetime.utcnow()}
        if title is not None:
            values["title"] = title
        if content is not None:
            values["content"] = content
        if tags is not None:
            values["tags"] = tags
        result = await session.execute(update(Note).where(Note.id == note_id).values(**values))
        return result.rowcount > 0

    @staticmethod
    async def delete(session: AsyncSession, note_id: str) -> bool:
        result = await session.execute(delete(Note).where(Note.id == note_id))
        return result.rowcount > 0

    @staticmethod
    async def search(session: AsyncSession, query: str) -> list[Note]:
        result = await session.execute(
            select(Note)
            .where(Note.title.ilike(f"%{query}%") | Note.content.ilike(f"%{query}%"))
            .order_by(desc(Note.created_at))
        )
        return list(result.scalars().all())


# ── Reminders ─────────────────────────────────────────────────

class ReminderRepo:
    @staticmethod
    async def create(
        session: AsyncSession,
        title: str,
        description: str = "",
        scheduled_at: Optional[datetime] = None,
    ) -> Reminder:
        rem = Reminder(
            id=new_id(), title=title, description=description, scheduled_at=scheduled_at
        )
        session.add(rem)
        await session.flush()
        return rem

    @staticmethod
    async def get(session: AsyncSession, rem_id: str) -> Optional[Reminder]:
        result = await session.execute(select(Reminder).where(Reminder.id == rem_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(session: AsyncSession, status: Optional[str] = None) -> list[Reminder]:
        q = select(Reminder)
        if status:
            q = q.where(Reminder.status == status)
        q = q.order_by(desc(Reminder.created_at))
        result = await session.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        session: AsyncSession,
        rem_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        scheduled_at: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> bool:
        values: dict = {}
        if title is not None:
            values["title"] = title
        if description is not None:
            values["description"] = description
        if scheduled_at is not None:
            values["scheduled_at"] = scheduled_at
        if status is not None:
            values["status"] = status
            if status == "completed":
                values["completed_at"] = datetime.utcnow()
        if not values:
            return False
        result = await session.execute(update(Reminder).where(Reminder.id == rem_id).values(**values))
        return result.rowcount > 0

    @staticmethod
    async def delete(session: AsyncSession, rem_id: str) -> bool:
        result = await session.execute(delete(Reminder).where(Reminder.id == rem_id))
        return result.rowcount > 0

    @staticmethod
    async def get_pending(session: AsyncSession) -> list[Reminder]:
        result = await session.execute(
            select(Reminder)
            .where(Reminder.status == "pending")
            .where(Reminder.scheduled_at <= datetime.utcnow())
            .order_by(Reminder.scheduled_at)
        )
        return list(result.scalars().all())


# ── Tool Executions ───────────────────────────────────────────

class ToolExecutionRepo:
    @staticmethod
    async def create(
        session: AsyncSession,
        tool_name: str,
        input_data: Optional[dict] = None,
        output_data: Optional[dict] = None,
        success: bool = True,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> ToolExecution:
        te = ToolExecution(
            id=new_id(),
            message_id=message_id,
            tool_name=tool_name,
            input_json=json.dumps(input_data) if input_data else None,
            output_json=json.dumps(output_data) if output_data else None,
            success=success,
            duration_ms=duration_ms,
            error_message=error_message,
        )
        session.add(te)
        await session.flush()
        return te


# ── System Events ─────────────────────────────────────────────

class SystemEventRepo:
    @staticmethod
    async def create(session: AsyncSession, event_type: str, details: Optional[str] = None) -> SystemEvent:
        evt = SystemEvent(id=new_id(), event_type=event_type, details=details)
        session.add(evt)
        await session.flush()
        return evt


# ── User Settings ─────────────────────────────────────────────

class SettingsRepo:
    @staticmethod
    async def get(session: AsyncSession, key: str) -> Optional[str]:
        result = await session.execute(select(UserSettings).where(UserSettings.key == key))
        row = result.scalar_one_or_none()
        return row.value if row else None

    @staticmethod
    async def set(session: AsyncSession, key: str, value: str) -> None:
        existing = await session.execute(select(UserSettings).where(UserSettings.key == key))
        row = existing.scalar_one_or_none()
        if row:
            row.value = value
        else:
            session.add(UserSettings(key=key, value=value))
        await session.flush()

    @staticmethod
    async def get_all(session: AsyncSession) -> dict[str, str]:
        result = await session.execute(select(UserSettings))
        return {row.key: row.value for row in result.scalars().all()}
