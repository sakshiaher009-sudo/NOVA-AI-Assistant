"""NOVA — LLM Schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    role: str  # system | user | assistant | tool
    content: str
    tool_calls: Optional[list[dict[str, Any]]] = None


class LLMRequest(BaseModel):
    model: str
    messages: list[LLMMessage]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[list[dict[str, Any]]] = None


class LLMResponse(BaseModel):
    content: str
    model: str
    total_duration_ns: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        if self.total_duration_ns:
            return int(self.total_duration_ns / 1_000_000)
        return 0


class ModelInfo(BaseModel):
    name: str
    size: Optional[int] = None
    modified_at: Optional[str] = None
    digest: Optional[str] = None
