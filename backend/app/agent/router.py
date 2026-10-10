"""NOVA — Agent Router.

Determines whether a user's request should be handled as:
  (a) a normal LLM conversation / question-answering
  (b) an actionable tool call

This logic is intentionally separated from the orchestrator so that
the routing strategy can be upgraded (e.g. to LLM-native function
calling) without touching core agent coordination code.
"""

from __future__ import annotations

from app.nlp.intent import Intent
from app.schemas.chat import NLPResult

# Intents that require tool execution (vs plain LLM conversation)
_TOOL_INTENTS: frozenset[str] = frozenset({
    Intent.CALCULATE.value,
    Intent.GET_TIME.value,
    Intent.CREATE_NOTE.value,
    Intent.LIST_NOTES.value,
    Intent.DELETE_NOTE.value,
    Intent.CREATE_REMINDER.value,
    Intent.OPEN_APPLICATION.value,
    Intent.OPEN_WEBSITE.value,
    Intent.OPEN_AMBIGUOUS.value,
    Intent.BROWSER_SEARCH.value,
    Intent.SEARCH_AMBIGUOUS.value,
    Intent.FILE_SEARCH.value,
    Intent.READ_FILE.value,
    Intent.EXECUTE_TERMINAL.value,
})

# Intents that require the RAG pipeline
_RAG_INTENTS: frozenset[str] = frozenset({
    Intent.DOCUMENT_SEARCH.value,
    Intent.DOCUMENT_SUMMARY.value,
})

# Intents that use internal handlers (not LLM, not tools)
_INTERNAL_INTENTS: frozenset[str] = frozenset({
    Intent.SEARCH_MEMORY.value,
    Intent.SYSTEM_STATUS.value,
})


def is_tool_call(nlp_result: NLPResult) -> bool:
    """Return True if this request should be routed to a tool."""
    return nlp_result.intent in _TOOL_INTENTS


def is_rag_call(nlp_result: NLPResult) -> bool:
    """Return True if this request should use the RAG pipeline."""
    return nlp_result.intent in _RAG_INTENTS


def is_internal_call(nlp_result: NLPResult) -> bool:
    """Return True if this request uses an internal handler (no LLM)."""
    return nlp_result.intent in _INTERNAL_INTENTS


def is_conversation(nlp_result: NLPResult) -> bool:
    """Return True if this should flow to the general LLM conversation."""
    return not (
        is_tool_call(nlp_result)
        or is_rag_call(nlp_result)
        or is_internal_call(nlp_result)
    )


def allows_llm_tool_calls(nlp_result: NLPResult) -> bool:
    """Allow native LLM tools only when NLP found an actionable tool intent."""
    return is_tool_call(nlp_result)


def route_description(nlp_result: NLPResult) -> str:
    """Return a human-readable description of the routing decision."""
    if is_tool_call(nlp_result):
        return f"tool_call[{nlp_result.intent}]"
    if is_rag_call(nlp_result):
        return f"rag[{nlp_result.intent}]"
    if is_internal_call(nlp_result):
        return f"internal[{nlp_result.intent}]"
    return f"conversation[{nlp_result.intent}]"
