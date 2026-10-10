"""NOVA — Tool Registry."""

from __future__ import annotations

from typing import Optional

import structlog

from app.tools.base import BaseTool, ToolResult
from app.tools.calculator import CalculatorTool
from app.tools.time_tool import TimeTool
from app.tools.notes import CreateNoteTool, ListNotesTool, DeleteNoteTool
from app.tools.reminders import CreateReminderTool
from app.tools.document_search import DocumentSearchTool
from app.tools.open_application import OpenApplicationTool
from app.tools.open_website import OpenWebsiteTool
from app.tools.browser_search import BrowserSearchTool
from app.tools.file_search import FileSearchTool
from app.tools.read_file import ReadFileTool
from app.tools.execute_terminal import ExecuteTerminalTool

logger = structlog.get_logger(__name__)

# Global registry
_tools: dict[str, BaseTool] = {}


def _register(tool: BaseTool) -> None:
    _tools[tool.name] = tool


def init_tools() -> None:
    """Initialize all available tools."""
    _register(CalculatorTool())
    _register(TimeTool())
    _register(CreateNoteTool())
    _register(ListNotesTool())
    _register(DeleteNoteTool())
    _register(CreateReminderTool())
    _register(DocumentSearchTool())
    _register(OpenApplicationTool())
    _register(OpenWebsiteTool())
    _register(BrowserSearchTool())
    _register(FileSearchTool())
    _register(ReadFileTool())
    _register(ExecuteTerminalTool())
    logger.info("tools_initialized", count=len(_tools), names=list(_tools.keys()))


def get_tool(name: str) -> Optional[BaseTool]:
    """Get a tool by name."""
    return _tools.get(name)


def list_tools() -> list[BaseTool]:
    """Return all registered tools."""
    return list(_tools.values())


def get_tools_description() -> str:
    """Return a formatted description of all tools for the LLM system prompt."""
    lines = []
    for tool in _tools.values():
        params_desc = ""
        if tool.parameters:
            params = ", ".join(f"{p.name}: {p.type}" for p in tool.parameters)
            params_desc = f" ({params})"
        lines.append(f"- {tool.name}{params_desc}: {tool.description}")
    return "\n".join(lines)


def get_tools_schema() -> list[dict]:
    """Return structured JSON schemas for all tools.

    This is the extensibility hook for future LLM-native function calling
    (e.g. Ollama tools API) — each entry is already in the format that
    most LLM APIs expect, so no changes to the core registry are needed.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        p.name: {
                            "type": p.type,
                            "description": p.description,
                        }
                        for p in tool.parameters
                    },
                    "required": [p.name for p in tool.parameters if p.required],
                },
            },
        }
        for tool in _tools.values()
    ]


# Map intents to tools
# To add a new tool: (1) create a tool class in app/tools/, (2) register it in init_tools(),
# (3) add a new entry here, (4) add the intent to app/agent/router._TOOL_INTENTS.
_INTENT_TOOL_MAP: dict[str, str] = {
    "CALCULATE": "calculator",
    "GET_TIME": "get_current_time",
    "CREATE_NOTE": "create_note",
    "LIST_NOTES": "list_notes",
    "DELETE_NOTE": "delete_note",
    "CREATE_REMINDER": "create_reminder",
    "DOCUMENT_SEARCH": "document_search",
    "DOCUMENT_SUMMARY": "document_search",
    "OPEN_APPLICATION": "open_app",
    "OPEN_WEBSITE": "open_website",
    "BROWSER_SEARCH": "browser_search",
    "FILE_SEARCH": "file_search",
    "READ_FILE": "read_file",
    "EXECUTE_TERMINAL": "execute_terminal",
}


def get_tool_for_intent(intent: str) -> Optional[BaseTool]:
    """Return the appropriate tool for a given intent."""
    tool_name = _INTENT_TOOL_MAP.get(intent)
    if tool_name:
        return get_tool(tool_name)
    return None
