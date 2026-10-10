"""NOVA — Pydantic Schemas for Voice."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TranscribeResponse(BaseModel):
    text: str
    language: str = "en"
    confidence: Optional[float] = None
    duration_ms: int = 0


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice: Optional[str] = None
    speed: Optional[float] = None


class VoiceRespondRequest(BaseModel):
    conversation_id: Optional[str] = None


class VoiceRespondResponse(BaseModel):
    message_id: str
    conversation_id: str
    transcript: str
    response: str
    stt_duration_ms: int = 0
    llm_duration_ms: int = 0
    tts_duration_ms: int = 0
    total_latency_ms: int = 0
