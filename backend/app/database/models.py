"""NOVA — SQLAlchemy Database Models."""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Boolean,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Declarative base for all models."""
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False, default="New Conversation")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    is_archived = Column(Boolean, default=False)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_conversations_updated", "updated_at"),)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=True)
    entities_json = Column(Text, nullable=True)  # JSON string
    tool_name = Column(String(50), nullable=True)
    tool_result_json = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    stt_duration_ms = Column(Integer, nullable=True)
    llm_duration_ms = Column(Integer, nullable=True)
    tts_duration_ms = Column(Integer, nullable=True)
    is_voice = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation", "conversation_id"),
        Index("ix_messages_created", "created_at"),
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_extension = Column(String(10), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    chunk_count = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending | processing | indexed | error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    char_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="chunks")

    __table_args__ = (Index("ix_chunks_document", "document_id"),)


class Memory(Base):
    __tablename__ = "memories"

    id = Column(String(36), primary_key=True)
    content = Column(Text, nullable=False)
    category = Column(String(50), default="general")
    source = Column(String(50), default="user")  # user | assistant
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Note(Base):
    __tablename__ = "notes"

    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False, default="")
    tags = Column(String(500), nullable=True)  # comma-separated
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (Index("ix_notes_created", "created_at"),)


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True, default="")
    scheduled_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")  # pending | completed | cancelled
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_reminders_status", "status"),
        Index("ix_reminders_scheduled", "scheduled_at"),
    )


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id = Column(String(36), primary_key=True)
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    tool_name = Column(String(50), nullable=False)
    input_json = Column(Text, nullable=True)
    output_json = Column(Text, nullable=True)
    success = Column(Boolean, default=True)
    duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_tool_exec_name", "tool_name"),)


class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(String(36), primary_key=True)
    event_type = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_events_type", "event_type"),)


class UserSettings(Base):
    __tablename__ = "user_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_users_email", "email"),)

