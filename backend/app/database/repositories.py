"""NOVA — Database Repository Layer (CRUD operations with User Scoping)."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import delete, desc, select, update
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
    async def create(
        session: AsyncSession,
        title: str = "New Conversation",
        user_id: str = "default_user",
    ) -> Conversation:
        conv = Conversation(id=new_id(), user_id=user_id, title=title)
        session.add(conv)
        await session.flush()
        return conv

    @staticmethod
    async def get(
        session: AsyncSession,
        conv_id: str,
        user_id: str | None = None,
    ) -> Conversation | None:
        q = select(Conversation).where(Conversation.id == conv_id)
        if user_id is not None:
            q = q.where(Conversation.user_id == user_id)
        result = await session.execute(q)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        session: AsyncSession,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[Conversation]:
        q = select(Conversation).where(Conversation.is_archived.is_(False))
        if user_id is not None:
            q = q.where(Conversation.user_id == user_id)
        q = q.order_by(desc(Conversation.updated_at)).limit(limit)
        result = await session.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def delete(
        session: AsyncSession,
        conv_id: str,
        user_id: str | None = None,
    ) -> bool:
        q = delete(Conversation).where(Conversation.id == conv_id)
        if user_id is not None:
            q = q.where(Conversation.user_id == user_id)
        result = await session.execute(q)
        return result.rowcount > 0

    @staticmethod
    async def update_title(
        session: AsyncSession,
        conv_id: str,
        title: str,
        user_id: str | None = None,
    ) -> bool:
        q = update(Conversation).where(Conversation.id == conv_id)
        if user_id is not None:
            q = q.where(Conversation.user_id == user_id)
        q = q.values(title=title, updated_at=datetime.utcnow())
        result = await session.execute(q)
        return result.rowcount > 0


# ── Messages ──────────────────────────────────────────────────

class MessageRepo:
    @staticmethod
    async def create(
        session: AsyncSession,
        conversation_id: str,
        role: str,
        content: str,
        user_id: str = "default_user",
        *,
        intent: str | None = None,
        confidence: float | None = None,
        entities: dict | None = None,
        tool_name: str | None = None,
        tool_result: dict | None = None,
        latency_ms: int | None = None,
        stt_duration_ms: int | None = None,
        llm_duration_ms: int | None = None,
        tts_duration_ms: int | None = None,
        is_voice: bool = False,
    ) -> Message:
        if not await ConversationRepo.get(session, conversation_id, user_id=user_id):
            raise ValueError("Conversation not found for this user")
        msg = Message(
            id=new_id(),
            user_id=user_id,
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
        # Update parent conversation timestamp
        await session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .values(updated_at=datetime.utcnow())
        )
        return msg

    @staticmethod
    async def get_by_conversation(
        session: AsyncSession,
        conversation_id: str,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[Message]:
        if user_id is not None:
            conv = await ConversationRepo.get(session, conversation_id, user_id=user_id)
            if not conv:
                return []
        q = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .limit(limit)
        )
        if user_id is not None:
            q = q.where(Message.user_id == user_id)
        result = await session.execute(q)
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
        user_id: str = "default_user",
    ) -> Document:
        doc = Document(
            id=new_id(),
            user_id=user_id,
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
    async def get(
        session: AsyncSession,
        doc_id: str,
        user_id: str | None = None,
    ) -> Document | None:
        q = select(Document).where(Document.id == doc_id)
        if user_id is not None:
            q = q.where(Document.user_id == user_id)
        result = await session.execute(q)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        session: AsyncSession,
        user_id: str | None = None,
    ) -> list[Document]:
        q = select(Document)
        if user_id is not None:
            q = q.where(Document.user_id == user_id)
        q = q.order_by(desc(Document.created_at))
        result = await session.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def update_status(
        session: AsyncSession,
        doc_id: str,
        status: str,
        chunk_count: int = 0,
        error_message: str | None = None,
        user_id: str | None = None,
    ) -> bool:
        q = update(Document).where(Document.id == doc_id)
        if user_id is not None:
            q = q.where(Document.user_id == user_id)
        q = q.values(
            status=status,
            chunk_count=chunk_count,
            error_message=error_message,
            updated_at=datetime.utcnow(),
        )
        result = await session.execute(q)
        return result.rowcount > 0

    @staticmethod
    async def delete(
        session: AsyncSession,
        doc_id: str,
        user_id: str | None = None,
    ) -> bool:
        q = delete(Document).where(Document.id == doc_id)
        if user_id is not None:
            q = q.where(Document.user_id == user_id)
        result = await session.execute(q)
        return result.rowcount > 0


class ChunkRepo:
    @staticmethod
    async def create_many(
        session: AsyncSession,
        document_id: str,
        chunks: list[str],
        user_id: str = "default_user",
    ) -> list[DocumentChunk]:
        if not await DocumentRepo.get(session, document_id, user_id=user_id):
            raise ValueError("Document not found for this user")
        records = []
        for i, text in enumerate(chunks):
            c = DocumentChunk(
                id=new_id(),
                user_id=user_id,
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
    async def get_by_document(
        session: AsyncSession,
        document_id: str,
        user_id: str | None = None,
    ) -> list[DocumentChunk]:
        if user_id is not None and not await DocumentRepo.get(
            session, document_id, user_id=user_id
        ):
            return []
        q = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        if user_id is not None:
            q = q.where(DocumentChunk.user_id == user_id)
        q = q.order_by(DocumentChunk.chunk_index)
        result = await session.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def delete_by_document(
        session: AsyncSession,
        document_id: str,
        user_id: str | None = None,
    ) -> None:
        if user_id is not None and not await DocumentRepo.get(
            session, document_id, user_id=user_id
        ):
            return
        q = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        if user_id is not None:
            q = q.where(DocumentChunk.user_id == user_id)
        await session.execute(q)


# ── Memory ────────────────────────────────────────────────────

class MemoryRepo:
    @staticmethod
    async def create(
        session: AsyncSession,
        content: str,
        category: str = "general",
        source: str = "user",
        user_id: str = "default_user",
    ) -> Memory:
        mem = Memory(
            id=new_id(),
            user_id=user_id,
            content=content,
            category=category,
            source=source,
        )
        session.add(mem)
        await session.flush()
        return mem

    @staticmethod
    async def get(
        session: AsyncSession,
        mem_id: str,
        user_id: str | None = None,
    ) -> Memory | None:
        q = select(Memory).where(Memory.id == mem_id)
        if user_id is not None:
            q = q.where(Memory.user_id == user_id)
        result = await session.execute(q)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        session: AsyncSession,
        user_id: str | None = None,
    ) -> list[Memory]:
        q = select(Memory)
        if user_id is not None:
            q = q.where(Memory.user_id == user_id)
        q = q.order_by(desc(Memory.created_at))
        result = await session.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def delete(
        session: AsyncSession,
        mem_id: str,
        user_id: str | None = None,
    ) -> bool:
        q = delete(Memory).where(Memory.id == mem_id)
        if user_id is not None:
            q = q.where(Memory.user_id == user_id)
        result = await session.execute(q)
        return result.rowcount > 0

    @staticmethod
    async def search(
        session: AsyncSession,
        query: str,
        user_id: str | None = None,
    ) -> list[Memory]:
        q = select(Memory).where(Memory.content.ilike(f"%{query}%"))
        if user_id is not None:
            q = q.where(Memory.user_id == user_id)
        q = q.order_by(desc(Memory.created_at))
        result = await session.execute(q)
        return list(result.scalars().all())


# ── Notes ─────────────────────────────────────────────────────

class NoteRepo:
    @staticmethod
    async def create(
        session: AsyncSession,
        title: str,
        content: str = "",
        tags: str = "",
        user_id: str = "default_user",
    ) -> Note:
        note = Note(
            id=new_id(),
            user_id=user_id,
            title=title,
            content=content,
            tags=tags,
        )
        session.add(note)
        await session.flush()
        return note

    @staticmethod
    async def get(
        session: AsyncSession,
        note_id: str,
        user_id: str | None = None,
    ) -> Note | None:
        q = select(Note).where(Note.id == note_id)
        if user_id is not None:
            q = q.where(Note.user_id == user_id)
        result = await session.execute(q)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        session: AsyncSession,
        user_id: str | None = None,
    ) -> list[Note]:
        q = select(Note)
        if user_id is not None:
            q = q.where(Note.user_id == user_id)
        q = q.order_by(desc(Note.created_at))
        result = await session.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        session: AsyncSession,
        note_id: str,
        title: str | None = None,
        content: str | None = None,
        tags: str | None = None,
        user_id: str | None = None,
    ) -> bool:
        values: dict = {"updated_at": datetime.utcnow()}
        if title is not None:
            values["title"] = title
        if content is not None:
            values["content"] = content
        if tags is not None:
            values["tags"] = tags

        q = update(Note).where(Note.id == note_id)
        if user_id is not None:
            q = q.where(Note.user_id == user_id)
        result = await session.execute(q.values(**values))
        return result.rowcount > 0

    @staticmethod
    async def delete(
        session: AsyncSession,
        note_id: str,
        user_id: str | None = None,
    ) -> bool:
        q = delete(Note).where(Note.id == note_id)
        if user_id is not None:
            q = q.where(Note.user_id == user_id)
        result = await session.execute(q)
        return result.rowcount > 0

    @staticmethod
    async def search(
        session: AsyncSession,
        query: str,
        user_id: str | None = None,
    ) -> list[Note]:
        q = select(Note).where(Note.title.ilike(f"%{query}%") | Note.content.ilike(f"%{query}%"))
        if user_id is not None:
            q = q.where(Note.user_id == user_id)
        q = q.order_by(desc(Note.created_at))
        result = await session.execute(q)
        return list(result.scalars().all())


# ── Reminders ─────────────────────────────────────────────────

class ReminderRepo:
    @staticmethod
    async def create(
        session: AsyncSession,
        title: str,
        description: str = "",
        scheduled_at: datetime | None = None,
        user_id: str = "default_user",
    ) -> Reminder:
        rem = Reminder(
            id=new_id(),
            user_id=user_id,
            title=title,
            description=description,
            scheduled_at=scheduled_at,
        )
        session.add(rem)
        await session.flush()
        return rem

    @staticmethod
    async def get(
        session: AsyncSession,
        rem_id: str,
        user_id: str | None = None,
    ) -> Reminder | None:
        q = select(Reminder).where(Reminder.id == rem_id)
        if user_id is not None:
            q = q.where(Reminder.user_id == user_id)
        result = await session.execute(q)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        session: AsyncSession,
        user_id: str | None = None,
        status: str | None = None,
    ) -> list[Reminder]:
        q = select(Reminder)
        if user_id is not None:
            q = q.where(Reminder.user_id == user_id)
        if status:
            q = q.where(Reminder.status == status)
        q = q.order_by(desc(Reminder.created_at))
        result = await session.execute(q)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        session: AsyncSession,
        rem_id: str,
        title: str | None = None,
        description: str | None = None,
        scheduled_at: datetime | None = None,
        status: str | None = None,
        user_id: str | None = None,
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

        q = update(Reminder).where(Reminder.id == rem_id)
        if user_id is not None:
            q = q.where(Reminder.user_id == user_id)
        result = await session.execute(q.values(**values))
        return result.rowcount > 0

    @staticmethod
    async def delete(
        session: AsyncSession,
        rem_id: str,
        user_id: str | None = None,
    ) -> bool:
        q = delete(Reminder).where(Reminder.id == rem_id)
        if user_id is not None:
            q = q.where(Reminder.user_id == user_id)
        result = await session.execute(q)
        return result.rowcount > 0

    @staticmethod
    async def get_pending(
        session: AsyncSession,
        user_id: str | None = None,
    ) -> list[Reminder]:
        q = (
            select(Reminder)
            .where(Reminder.status == "pending")
            .where(Reminder.scheduled_at <= datetime.utcnow())
        )
        if user_id is not None:
            q = q.where(Reminder.user_id == user_id)
        q = q.order_by(Reminder.scheduled_at)
        result = await session.execute(q)
        return list(result.scalars().all())


# ── Tool Executions ───────────────────────────────────────────

class ToolExecutionRepo:
    @staticmethod
    async def create(
        session: AsyncSession,
        tool_name: str,
        input_data: dict | None = None,
        output_data: dict | None = None,
        success: bool = True,
        duration_ms: int | None = None,
        error_message: str | None = None,
        message_id: str | None = None,
        user_id: str = "default_user",
    ) -> ToolExecution:
        if message_id is not None:
            result = await session.execute(
                select(Message.id).where(
                    Message.id == message_id,
                    Message.user_id == user_id,
                )
            )
            if result.scalar_one_or_none() is None:
                raise ValueError("Message not found for this user")
        te = ToolExecution(
            id=new_id(),
            user_id=user_id,
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
    async def create(
        session: AsyncSession,
        event_type: str,
        details: str | None = None,
    ) -> SystemEvent:
        evt = SystemEvent(id=new_id(), event_type=event_type, details=details)
        session.add(evt)
        await session.flush()
        return evt


# ── User Settings ─────────────────────────────────────────────

class SettingsRepo:
    @staticmethod
    async def get(
        session: AsyncSession,
        key: str,
        user_id: str = "default_user",
    ) -> str | None:
        result = await session.execute(
            select(UserSettings).where(
                UserSettings.user_id == user_id,
                UserSettings.key == key,
            )
        )
        row = result.scalar_one_or_none()
        return row.value if row else None

    @staticmethod
    async def set(
        session: AsyncSession,
        key: str,
        value: str,
        user_id: str = "default_user",
    ) -> None:
        existing = await session.execute(
            select(UserSettings).where(
                UserSettings.user_id == user_id,
                UserSettings.key == key,
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            row.value = value
        else:
            session.add(UserSettings(user_id=user_id, key=key, value=value))
        await session.flush()

    @staticmethod
    async def get_all(
        session: AsyncSession,
        user_id: str = "default_user",
    ) -> dict[str, str]:
        result = await session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        return {row.key: row.value for row in result.scalars().all()}
