"""NOVA — Response Formatter."""

from __future__ import annotations

from app.tools.base import ToolResult as ToolExecResult


def format_tool_response(tool_name: str, result: ToolExecResult) -> str:
    """Format a tool execution result into a natural language response."""
    if not result.success:
        return f"I tried to use the {tool_name} tool, but encountered an error: {result.error}"

    if result.display_text:
        return result.display_text

    if result.result is not None:
        return str(result.result)

    return "Done."


def format_error_response(error_type: str) -> str:
    """Return a user-friendly error message."""
    messages = {
        "ollama_unavailable": (
            "The local language model is currently unavailable. "
            "Please make sure Ollama is running (`ollama serve`) and try again."
        ),
        "model_unavailable": (
            "The configured AI model is not available. "
            "Please run `ollama pull <model_name>` to download it."
        ),
        "stt_unavailable": (
            "Speech recognition is currently unavailable. "
            "Please check the STT configuration."
        ),
        "tts_unavailable": (
            "Voice synthesis is currently unavailable. "
            "The response will be displayed as text only."
        ),
        "document_parse_error": "Unable to process this document. Please check the file format.",
        "general": "Something went wrong. Please try again.",
    }
    return messages.get(error_type, messages["general"])
