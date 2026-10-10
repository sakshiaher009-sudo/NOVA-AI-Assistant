"""NOVA — Intent Classification.

Uses deterministic keyword/pattern matching for common intents,
with LLM fallback for ambiguous cases.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class Intent(str, Enum):
    GENERAL_CONVERSATION = "GENERAL_CONVERSATION"
    QUESTION_ANSWERING = "QUESTION_ANSWERING"
    DOCUMENT_SEARCH = "DOCUMENT_SEARCH"
    DOCUMENT_SUMMARY = "DOCUMENT_SUMMARY"
    CREATE_NOTE = "CREATE_NOTE"
    LIST_NOTES = "LIST_NOTES"
    DELETE_NOTE = "DELETE_NOTE"
    CREATE_REMINDER = "CREATE_REMINDER"
    CALCULATE = "CALCULATE"
    GET_TIME = "GET_TIME"
    SEARCH_MEMORY = "SEARCH_MEMORY"
    SYSTEM_STATUS = "SYSTEM_STATUS"
    OPEN_APPLICATION = "OPEN_APPLICATION"
    OPEN_WEBSITE = "OPEN_WEBSITE"
    OPEN_AMBIGUOUS = "OPEN_AMBIGUOUS"
    BROWSER_SEARCH = "BROWSER_SEARCH"
    SEARCH_AMBIGUOUS = "SEARCH_AMBIGUOUS"
    FOLLOWUP_ACKNOWLEDGEMENT = "FOLLOWUP_ACKNOWLEDGEMENT"
    FILE_SEARCH = "FILE_SEARCH"
    READ_FILE = "READ_FILE"
    EXECUTE_TERMINAL = "EXECUTE_TERMINAL"
    UNKNOWN = "UNKNOWN"


# Pattern-based rules: (compiled regex, intent, confidence)
_RULES: list[tuple[re.Pattern, Intent, float]] = [
    # Core desktop and file tools
    (re.compile(r"\b(?:open|launch|start)\s+(?:the\s+)?(?:app|application)\s+[a-z0-9][\w .-]*|\b(?:open|launch|start)\s+(?!this\s+(?:text\s+)?file\b|the\s+(?:text\s+)?file\b)[a-z0-9][\w .-]*", re.I), Intent.OPEN_APPLICATION, 0.95),
    (re.compile(r"\b(?:find|locate|search\s+for)\b.*\b(?:notes?|files?|documents?)\b", re.I), Intent.FILE_SEARCH, 0.93),
    (re.compile(r"\b(?:read|open)\s+(?:this|the|my)?\s*(?:text\s+)?file\b", re.I), Intent.READ_FILE, 0.94),
    (re.compile(r"\b(?:check|show|get|run|execute)\b.*\b(?:python|node|npm|version|terminal|command)\b", re.I), Intent.EXECUTE_TERMINAL, 0.91),

    # Calculator — math expressions
    (re.compile(r"(?:what\s+is\s+|calculate\s+|compute\s+|solve\s+)?\d+[\s]*[\+\-\*\/\%\^][\s]*\d+", re.I), Intent.CALCULATE, 0.95),
    (re.compile(r"\b(?:calculate|compute|solve|math|evaluate)\b.*\d", re.I), Intent.CALCULATE, 0.90),
    (re.compile(r"\b(?:calculate|compute|solve)\s+(?:it|that|this)\b", re.I), Intent.CALCULATE, 0.86),
    (re.compile(r"\b\d+(?:\.\d+)?\s*percent\s+of\s+\d+(?:\.\d+)?\b", re.I), Intent.CALCULATE, 0.95),
    (re.compile(r"^\d+[\s]*[\+\-\*\/\%\^][\s]*\d+[\s]*(?:[\+\-\*\/\%\^][\s]*\d+)*\s*[=\?]?\s*$", re.I), Intent.CALCULATE, 0.97),

    # Time — comprehensive patterns covering natural voice queries
    (re.compile(r"\b(?:what(?:'s|\s+is)\s+(?:the\s+)?(?:current\s+)?(?:time|date|day)(?:\s+(?:is\s+it|now|right\s+now)?)?)\b", re.I), Intent.GET_TIME, 0.96),
    (re.compile(r"\b(?:current\s+(?:time|date|day)|time\s+(?:now|right\s+now)|today'?s?\s+date)\b", re.I), Intent.GET_TIME, 0.95),
    (re.compile(r"\b(?:tell\s+me\s+the\s+(?:time|date)|give\s+me\s+the\s+(?:time|date))\b", re.I), Intent.GET_TIME, 0.93),
    (re.compile(r"^(?:time|date|day|what\s+time)[?.]?\s*$", re.I), Intent.GET_TIME, 0.90),
    (re.compile(r"\b(?:time\s+please|what\s+time\s+is\s+it|it\s+is\s+what\s+time)\b", re.I), Intent.GET_TIME, 0.92),
    (re.compile(r"\bhow\s+late\s+is\s+it\b", re.I), Intent.GET_TIME, 0.88),

    # Notes — create
    (re.compile(r"\b(?:remember\s+(?:that|to)|save\s+(?:a\s+)?note|create\s+(?:a\s+)?note|note\s+(?:that|down)|make\s+a\s+note|jot\s+down|write\s+down)\b", re.I), Intent.CREATE_NOTE, 0.92),
    (re.compile(r"\b(?:keep\s+in\s+mind|don'?t\s+(?:let\s+me\s+)?forget)\b", re.I), Intent.CREATE_NOTE, 0.88),

    # Notes — list
    (re.compile(r"\b(?:show|list|display|view|get)\s+(?:my\s+|all\s+)?notes?\b", re.I), Intent.LIST_NOTES, 0.93),
    (re.compile(r"\bwhat\s+(?:are\s+)?my\s+notes\b", re.I), Intent.LIST_NOTES, 0.91),

    # Notes — delete
    (re.compile(r"\b(?:delete|remove|clear|erase)\s+(?:the\s+|a\s+|my\s+)?note\b", re.I), Intent.DELETE_NOTE, 0.90),

    # Reminders
    (re.compile(r"\b(?:remind\s+me|set\s+(?:a\s+)?reminder|create\s+(?:a\s+)?reminder|add\s+(?:a\s+)?reminder)\b", re.I), Intent.CREATE_REMINDER, 0.94),
    (re.compile(r"\b(?:reminder\s+(?:to|for|about))\b", re.I), Intent.CREATE_REMINDER, 0.88),

    # Document search
    (re.compile(r"\b(?:find|search|look\s+(?:up|for)|locate)\b.*\b(?:my\s+)?(?:documents?|pdfs?|uploads?)\b", re.I), Intent.DOCUMENT_SEARCH, 0.94),
    (re.compile(r"\b(?:find|search|look\s+(?:up|for)|locate)\b.*\b(?:in\s+(?:my\s+)?(?:document|pdf|file|upload)s?|document|pdf|file)\b", re.I), Intent.DOCUMENT_SEARCH, 0.92),
    (re.compile(r"\b(?:what\s+does|according\s+to)\s+(?:the\s+|my\s+)?(?:document|pdf|file)\b", re.I), Intent.DOCUMENT_SEARCH, 0.90),
    (re.compile(r"\b(?:in\s+(?:the|my)\s+(?:uploaded?\s+)?(?:document|pdf|file)s?)\b", re.I), Intent.DOCUMENT_SEARCH, 0.88),

    # Document summary
    (re.compile(r"\b(?:summarize|summary\s+of|summarise|give\s+(?:me\s+)?(?:a\s+)?summary)\b.*\b(?:document|pdf|file|upload)?\b", re.I), Intent.DOCUMENT_SUMMARY, 0.90),

    # Memory search
    (re.compile(r"\b(?:what\s+(?:did\s+)?(?:i|you)\s+(?:say|tell|mention|note)|search\s+(?:my\s+)?memory|recall|do\s+you\s+remember)\b", re.I), Intent.SEARCH_MEMORY, 0.88),

    # System status
    (re.compile(r"\b(?:system\s+status|how\s+are\s+you|are\s+you\s+(?:working|ok|running)|status\s+check|health\s+check)\b", re.I), Intent.SYSTEM_STATUS, 0.90),

    # Question answering (generic questions)
    (re.compile(r"^(?:what|who|where|when|why|how|which|can\s+you|could\s+you|tell\s+me|explain|describe|define)\b", re.I), Intent.QUESTION_ANSWERING, 0.70),
]


def classify_intent(text: str) -> tuple[Intent, float]:
    """
    Classify user intent using deterministic pattern matching.

    Returns (intent, confidence) tuple.
    """
    if not text or not text.strip():
        return Intent.UNKNOWN, 0.0

    cleaned = text.strip()

    # Try each rule in priority order
    best_intent = Intent.UNKNOWN
    best_confidence = 0.0

    for pattern, intent, confidence in _RULES:
        if pattern.search(cleaned):
            if confidence > best_confidence:
                best_intent = intent
                best_confidence = confidence

    # If no high-confidence match, check for general conversation markers
    if best_confidence < 0.5:
        # Greeting patterns
        if re.match(r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|howdy|sup|yo)\b", cleaned, re.I):
            return Intent.GENERAL_CONVERSATION, 0.85

        # Thanks/farewell
        if re.match(r"^(?:thanks?|thank\s+you|bye|goodbye|see\s+you|good\s*bye)\b", cleaned, re.I):
            return Intent.GENERAL_CONVERSATION, 0.85

        # Very short input likely conversational
        if len(cleaned.split()) <= 3 and best_confidence < 0.3:
            return Intent.GENERAL_CONVERSATION, 0.50

    if best_confidence > 0:
        return best_intent, best_confidence

    return Intent.GENERAL_CONVERSATION, 0.40


async def classify_intent_with_llm(text: str) -> tuple[Intent, float]:
    """
    Use the local LLM for intent classification when pattern matching is ambiguous.
    Falls back to pattern matching if LLM is unavailable.
    """
    try:
        from app.llm import ollama_client

        intent_names = ", ".join(i.value for i in Intent)
        prompt = (
            f"Classify the following user message into exactly one intent.\n"
            f"Available intents: {intent_names}\n\n"
            f"User message: \"{text}\"\n\n"
            f"Respond with ONLY the intent name, nothing else."
        )
        result = await ollama_client.generate(prompt, temperature=0.1)
        result = result.strip().upper().replace(" ", "_")

        # Try to match to a valid Intent
        for intent in Intent:
            if intent.value in result:
                return intent, 0.80

    except Exception as e:
        logger.warning("llm_intent_classification_failed", error=str(e))

    # Fall back to pattern matching
    return classify_intent(text)
