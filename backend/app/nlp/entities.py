"""NOVA — Entity Extraction.

Uses regex patterns for structured entities (dates, times, numbers)
and LLM fallback for semantic entities (topics, tasks).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


def extract_entities(text: str) -> dict[str, Any]:
    """
    Extract entities from text using deterministic methods.

    Returns dict with entity types as keys and extracted values.
    """
    entities: dict[str, Any] = {}

    if not text:
        return entities

    app_match = re.search(r"\b(?:open|launch|start)\s+(?:the\s+)?(?:app|application)?\s*(.+?)[.!?]?$", text, re.I)
    if app_match:
        entities["app_name"] = app_match.group(1).strip()

    file_path_match = re.search(r"(?:read|open)\s+(?:this|the|my)?\s*(?:text\s+)?file\s*[:：]?\s*(.+)$", text, re.I)
    if file_path_match:
        entities["file_path"] = file_path_match.group(1).strip().strip('"\'')

    search_match = re.search(r"\b(?:find|locate|search\s+for)\s+(?:my\s+|the\s+)?(.+?)(?:\s+in\s+(?:my\s+)?(?:files?|documents?|folders?))?[.!?]?$", text, re.I)
    if search_match:
        entities["search_query"] = search_match.group(1).strip()

    browser_search_match = re.search(
        r"^(?:search|look\s+up|google)\s+(?:google\s+for\s+)?(.+?)[.!?]?$",
        text.strip(),
        re.I,
    )
    if browser_search_match:
        entities["browser_query"] = browser_search_match.group(1).strip()

    terminal_match = re.search(r"(?:run|execute)\s+(?:the\s+)?command\s*[:：]?\s*(.+)$", text, re.I)
    if terminal_match:
        entities["command"] = terminal_match.group(1).strip()
    elif re.search(r"\bpython\s+version\b", text, re.I):
        entities["command"] = "python3 --version"
    elif re.search(r"\bnode\s+version\b", text, re.I):
        entities["command"] = "node --version"

    # Numbers
    numbers = re.findall(r"\b\d+(?:\.\d+)?\b", text)
    if numbers:
        entities["numbers"] = [float(n) if "." in n else int(n) for n in numbers]

    # Math expression
    math_match = re.search(r"(\d+[\s]*[\+\-\*\/\%\^][\s]*\d+(?:[\s]*[\+\-\*\/\%\^][\s]*\d+)*)", text)
    if math_match:
        entities["math_expression"] = math_match.group(1).strip()
    percent_match = re.search(r"(\d+(?:\.\d+)?)\s*percent\s+of\s+(\d+(?:\.\d+)?)", text, re.I)
    if percent_match:
        entities["math_expression"] = f"({percent_match.group(1)} / 100) * {percent_match.group(2)}"

    # Time patterns
    time_match = re.search(
        r"\b(\d{1,2})\s*:\s*(\d{2})\s*(am|pm|AM|PM)?\b"
        r"|\b(\d{1,2})\s*(am|pm|AM|PM)\b"
        r"|\b(noon|midnight)\b",
        text,
    )
    if time_match:
        entities["time"] = time_match.group(0).strip()

    # Relative time expressions
    rel_time = re.search(
        r"\b(?:in\s+)?(\d+)\s*(minutes?|hours?|mins?|hrs?)\b"
        r"|\b(tonight|this\s+(?:morning|afternoon|evening))\b",
        text, re.I,
    )
    if rel_time:
        entities["relative_time"] = rel_time.group(0).strip()

    # Date patterns
    date_match = re.search(
        r"\b(?:today|tomorrow|yesterday"
        r"|(?:next|this)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month)"
        r"|(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"|\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?"
        r"|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})\b",
        text, re.I,
    )
    if date_match:
        entities["date"] = date_match.group(0).strip()

    # Duration
    duration_match = re.search(
        r"\b(\d+)\s*(?:minutes?|hours?|days?|weeks?|months?|mins?|hrs?)\b",
        text, re.I,
    )
    if duration_match:
        entities["duration"] = duration_match.group(0).strip()

    # Task/action — extract what comes after intent keywords
    task_match = re.search(
        r"(?:(?:remember|remind\s+me)\s+(?:to|that)\s+)(.+?)(?:\s+(?:at|on|by|tomorrow|today|tonight)\b|$)",
        text, re.I,
    )
    if task_match:
        entities["task"] = task_match.group(1).strip().rstrip(".")

    # Topic — extract from "about X" or "regarding X"
    topic_match = re.search(
        r"(?:about|regarding|on\s+the\s+topic\s+of|related\s+to)\s+(.+?)(?:\s+(?:in|from|at|on)\b|[\.!?\,]|$)",
        text, re.I,
    )
    if topic_match:
        entities["topic"] = topic_match.group(1).strip()

    # Document reference
    doc_match = re.search(
        r"(?:in\s+(?:the|my)\s+)?(?:uploaded?\s+)?(\w+\.(?:pdf|txt|md|docx))\b"
        r"|(?:(?:the|my)\s+)?(\w+(?:\s+\w+)*?)\s+(?:pdf|document|file)\b",
        text, re.I,
    )
    if doc_match:
        entities["document"] = (doc_match.group(1) or doc_match.group(2) or "").strip()

    return entities


def resolve_date(date_str: str) -> Optional[datetime]:
    """Resolve a date string to a datetime object."""
    now = datetime.now()
    lower = date_str.lower().strip()

    if lower == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif lower == "tomorrow":
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif lower == "yesterday":
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # Try dateparser if available
    try:
        import dateparser
        parsed = dateparser.parse(date_str, settings={"PREFER_DATES_FROM": "future"})
        if parsed:
            return parsed
    except ImportError:
        pass

    return None


def resolve_time(time_str: str) -> Optional[str]:
    """Resolve time string to HH:MM format."""
    lower = time_str.lower().strip()

    if lower == "noon":
        return "12:00"
    elif lower == "midnight":
        return "00:00"

    # Match "7 PM" or "7:30 PM" or "19:30"
    match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", lower)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        period = match.group(3)

        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    return None
