"""Nova Pipeline — Tool Registry.

Instance-based registry (no global state) that the orchestrator creates
and owns.  Tools are registered explicitly — call ``register()`` or use
``register_defaults()`` to add built-in tools.
"""

from __future__ import annotations

from typing import Optional

import structlog

from nova.interfaces import ToolSchema
from nova.tools.base_tool import NovaTool

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """Registry of available tools for the Nova pipeline.

    Unlike a global registry, each ``NovaPipeline`` instance owns its own
    ``ToolRegistry``, making the pipeline fully testable with mock tools.

    Usage::

        registry = ToolRegistry()
        registry.register(MyCustomTool())
        tool = registry.get("my_custom_tool")
    """

    def __init__(self) -> None:
        self._tools: dict[str, NovaTool] = {}

    def register(self, tool: NovaTool) -> None:
        """Register a tool.

        Args:
            tool: The tool instance to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered.  "
                f"Use a unique name or unregister the existing one first."
            )
        self._tools[tool.name] = tool
        logger.debug("nova_tool_registered", tool=tool.name)

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name.

        Returns:
            True if the tool was removed, False if it wasn't registered.
        """
        if name in self._tools:
            del self._tools[name]
            logger.debug("nova_tool_unregistered", tool=name)
            return True
        return False

    def get(self, name: str) -> Optional[NovaTool]:
        """Look up a tool by name.

        Returns:
            The tool instance, or ``None`` if not found.
        """
        return self._tools.get(name)

    def list_all(self) -> list[NovaTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get_schemas(self) -> list[ToolSchema]:
        """Return schemas for all registered tools (for the planner)."""
        return [tool.schema for tool in self._tools.values()]

    def get_names(self) -> list[str]:
        """Return the names of all registered tools."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={list(self._tools.keys())})"
