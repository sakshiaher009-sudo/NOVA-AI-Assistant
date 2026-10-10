"""NOVA — Pydantic Schemas for Chat & Conversations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Chat ──────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: Optional[str] = None


class EntityResult(BaseModel):
    type: str
    value: str
    raw: Optional[str] = None


class NLPResult(BaseModel):
    intent: str = "UNKNOWN"
    confidence: float = 0.0
    entities: dict[str, Any] = Field(default_factory=dict)
    language: str = "en"


class ToolResult(BaseModel):
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None


class PlanStatus(BaseModel):
    goal: str
    status: str
    current_step: Optional[int] = None
    completed_steps: list[int] = Field(default_factory=list)
    total_steps: int = 0


class ChatResponse(BaseModel):
    message_id: str
    conversation_id: str
    response: str
    nlp: Optional[NLPResult] = None
    tool: Optional[ToolResult] = None
    latency_ms: int = 0
    llm_duration_ms: int = 0
    agent_state: str = "idle"  # AgentState value after processing
    plan: Optional[PlanStatus] = None


# ── Conversations ─────────────────────────────────────────────

class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list["MessageOut"] = []

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    tool_name: Optional[str] = None
    is_voice: bool = False
    latency_ms: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    title: str = "New Conversation"
