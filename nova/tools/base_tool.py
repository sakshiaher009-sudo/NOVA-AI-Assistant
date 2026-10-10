"""Nova Pipeline — Abstract Tool Base Class.

All nova-specific tools inherit from ``NovaTool``.  This provides the
same contract as the existing project's ``BaseTool`` (validation, safe
execution, schema generation) but lives entirely within ``nova/``.

To add a new tool:
  1. Create a file in ``nova/tools/`` with a class extending ``NovaTool``.
  2. Override ``name``, ``description``, and ``execute``.
  3. Optionally override ``parameters`` to describe inputs.
  4. Register it in a ``ToolRegistry`` instance.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import structlog

from nova.interfaces import ToolParameter, ToolResult, ToolSchema

logger = structlog.get_logger(__name__)


class NovaTool(ABC):
    """Abstract base class for all Nova pipeline tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name (snake_case)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        ...

    @property
    def parameters(self) -> list[ToolParameter]:
        """Tool parameters.  Override in subclasses to describe inputs."""
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
        """Validate input parameters.

        Returns:
            An error string if validation fails, or ``None`` if valid.
        """
        for p in self.parameters:
            if p.required and p.name not in params:
                return f"Missing required parameter: {p.name}"
        return None

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute the tool with the given parameters.

        Subclasses implement this method with their specific logic.

        Args:
            params: Validated keyword arguments.

        Returns:
            A ``ToolResult`` with the outcome.
        """
        ...

    async def safe_execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute with input validation and error handling.

        Validates parameters first, then delegates to ``execute()``.
        Catches all exceptions and returns a failed ``ToolResult``
        instead of propagating.
        """
        validation_error = self.validate_input(params)
        if validation_error:
            return ToolResult(success=False, error=validation_error)

        try:
            start = time.perf_counter()
            result = await self.execute(params)
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "nova_tool_executed",
                tool=self.name,
                success=result.success,
                duration_ms=duration_ms,
            )
            return result
        except Exception as exc:
            logger.error(
                "nova_tool_execution_failed",
                tool=self.name,
                error=str(exc),
            )
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {exc}",
            )
