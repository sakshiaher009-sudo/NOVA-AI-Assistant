"""NOVA — Tool Base Class & Registry."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class ToolParameter(BaseModel):
    """Describes a single tool parameter."""
    name: str
    type: str  # string, number, boolean
    description: str
    required: bool = True
    default: Optional[Any] = None


class ToolSchema(BaseModel):
    """Schema describing a tool for the LLM."""
    name: str
    description: str
    parameters: list[ToolParameter] = []


class ToolResult(BaseModel):
    """Result from a tool execution."""
    success: bool = True
    result: Any = None
    error: Optional[str] = None
    display_text: Optional[str] = None


class BaseTool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        ...

    @property
    def parameters(self) -> list[ToolParameter]:
        """Tool parameters. Override in subclasses."""
        return []

    @property
    def schema(self) -> ToolSchema:
        """Return the tool schema for LLM consumption."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    def validate_input(self, params: dict[str, Any]) -> Optional[str]:
        """Validate input parameters. Return error string or None if valid."""
        for p in self.parameters:
            if p.required and p.name not in params:
                return f"Missing required parameter: {p.name}"
        return None

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute the tool with validated parameters."""
        ...

    async def safe_execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute with validation and error handling."""
        validation_error = self.validate_input(params)
        if validation_error:
            return ToolResult(success=False, error=validation_error)
        try:
            start = time.perf_counter()
            result = await self.execute(params)
            duration = (time.perf_counter() - start) * 1000
            logger.info("tool_executed", tool=self.name, duration_ms=round(duration))
            return result
        except Exception as e:
            logger.error("tool_execution_failed", tool=self.name, error=str(e))
            return ToolResult(success=False, error=f"Tool execution failed: {str(e)}")
