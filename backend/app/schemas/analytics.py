"""NOVA — Pydantic Schemas for Analytics, Notes, Reminders, Memory, Settings."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Analytics ─────────────────────────────────────────────────

class AnalyticsOverview(BaseModel):
    total_conversations: int = 0
    total_messages: int = 0
    voice_requests: int = 0
    avg_response_latency_ms: float = 0.0
    avg_stt_duration_ms: float = 0.0
    avg_llm_duration_ms: float = 0.0
    avg_tts_duration_ms: float = 0.0
    rag_searches: int = 0
    tool_executions: int = 0
    total_errors: int = 0
    intent_distribution: dict[str, int] = Field(default_factory=dict)
    tool_usage: dict[str, int] = Field(default_factory=dict)
    messages_per_day: list[dict[str, Any]] = Field(default_factory=list)


# ── Notes ─────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = ""
    tags: str = ""


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    tags: Optional[str] = None


class NoteOut(BaseModel):
    id: str
    title: str
    content: str
    tags: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Reminders ─────────────────────────────────────────────────

class ReminderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    scheduled_at: Optional[datetime] = None


class ReminderUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None


class ReminderOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Memory ────────────────────────────────────────────────────

class MemoryCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    category: str = "general"


class MemoryOut(BaseModel):
    id: str
    content: str
    category: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Settings ──────────────────────────────────────────────────

class SettingUpdate(BaseModel):
    key: str
    value: str


# ── Status ────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    app_name: str = "NOVA"
    version: str = "1.0.0"


class StatusResponse(BaseModel):
    status: str = "ok"
    ollama_available: bool = False
    ollama_model: str = ""
    stt_available: bool = False
    tts_available: bool = False
    database_ok: bool = False
    vector_db_ok: bool = False
