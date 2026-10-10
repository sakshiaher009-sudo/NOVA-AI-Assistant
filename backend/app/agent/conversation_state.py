"""Compact short-term conversational intelligence for NOVA."""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.nlp.intent import Intent


class ConversationState(BaseModel):
    current_topic: Optional[str] = None
    previous_topic: Optional[str] = None
    user_goal: Optional[str] = None
    current_intent: str = Intent.GENERAL_CONVERSATION.value
    entities: dict[str, Any] = Field(default_factory=dict)
    unresolved_references: list[str] = Field(default_factory=list)
    current_task: Optional[str] = None
    pending_action: Optional[str] = None
    missing_information: list[str] = Field(default_factory=list)
    previous_intent: Optional[str] = None
    previous_tool: Optional[str] = None
    previous_tool_result: Any = None
    response_strategy: str = "CASUAL_RESPONSE"
    confidence: float = 0.0
    task_status: str = "idle"
    predicted_next_action: str = "ANSWER"
    prediction_confidence: float = 0.0


def _topic(message: str, entities: dict[str, Any], previous: Optional[str]) -> Optional[str]:
    for key in ("topic", "app_name", "browser_query", "search_query", "math_expression"):
        value = entities.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().rstrip("?.")

    comparison = re.search(r"\b(?:compare|versus|vs\.?)\s+(.+)", message, re.I)
    if comparison:
        return comparison.group(1).strip().rstrip("?.")

    if re.search(r"\b(?:it|this|that|its|they|them|which one)\b", message, re.I):
        return previous

    question = re.search(
        r"\b(?:what is|what are|tell me about|explain)\s+(.+?)[?.]?$",
        message,
        re.I,
    )
    if question:
        return question.group(1).strip()

    learning = re.search(r"\b(?:learning|learn|studying)\s+([A-Za-z][\w+-]*)", message, re.I)
    if learning:
        return learning.group(1)

    words = re.findall(r"[A-Za-z][A-Za-z0-9+-]*", message)
    return " ".join(words[-5:]) if words else previous


def _strategy(intent: str, message: str) -> str:
    if intent in {Intent.OPEN_APPLICATION.value, Intent.OPEN_WEBSITE.value, Intent.BROWSER_SEARCH.value}:
        return "TASK_EXECUTION"
    if intent in {Intent.CALCULATE.value, Intent.GET_TIME.value}:
        return "DIRECT_ANSWER"
    if intent in {Intent.DOCUMENT_SEARCH.value, Intent.FILE_SEARCH.value}:
        return "TASK_EXECUTION"
    if re.search(
        r"\b(?:error|fails?|failed|broken|crash(?:es|ed)?|not working|issue|problem|debug)\b",
        message,
        re.I,
    ):
        return "TROUBLESHOOTING"
    if re.search(r"\b(?:compare|versus|vs\.?)\b", message, re.I):
        return "COMPARISON"
    if re.search(r"\b(?:why|how|what is|explain|tell me about)\b", message, re.I):
        return "EXPLANATION"
    if re.match(
        r"^(?:thanks?|thank you|hi|hello|hey|good morning|good afternoon|good evening|bye)\b",
        message.strip(),
        re.I,
    ):
        return "CASUAL_RESPONSE"
    if intent in {Intent.QUESTION_ANSWERING.value, Intent.GENERAL_CONVERSATION.value}:
        return "DIRECT_ANSWER"
    return "CASUAL_RESPONSE"


def build_conversation_state(
    message: str,
    intent: str,
    confidence: float,
    entities: dict[str, Any],
    previous: Optional[ConversationState] = None,
    tool_name: Optional[str] = None,
    tool_result: Any = None,
) -> ConversationState:
    previous_topic = previous.current_topic if previous else None
    current_topic = _topic(message, entities, previous_topic)
    references = re.findall(
        r"\b(?:it|this|that|they|them|its|which one|the first one|the second one)\b",
        message,
        re.I,
    )

    missing: list[str] = []
    next_action = "ANSWER"
    if intent == Intent.CREATE_REMINDER.value and not entities.get("task"):
        missing.append("reminder content")
        next_action = "ASK_MISSING_INFORMATION"
    elif intent == Intent.CALCULATE.value and not entities.get("math_expression"):
        missing.append("expression")
        next_action = "ASK_MISSING_INFORMATION"
    elif intent in {
        Intent.OPEN_APPLICATION.value,
        Intent.OPEN_WEBSITE.value,
        Intent.BROWSER_SEARCH.value,
    }:
        next_action = "EXECUTE_TOOL"
    elif (
        references
        and previous_topic
        and intent not in {
            Intent.GET_TIME.value,
            Intent.CALCULATE.value,
            Intent.OPEN_APPLICATION.value,
            Intent.OPEN_WEBSITE.value,
            Intent.BROWSER_SEARCH.value,
        }
    ):
        next_action = "CONTINUE_CONTEXT"

    goal = (
        "learn"
        if re.search(r"\b(?:learn|learning|understand|study|studying)\b", message, re.I)
        else None
    )
    return ConversationState(
        current_topic=current_topic,
        previous_topic=previous_topic,
        user_goal=goal or (previous.user_goal if previous else None),
        current_intent=intent,
        entities=entities,
        unresolved_references=references,
        previous_intent=previous.current_intent if previous else None,
        previous_tool=tool_name or (previous.previous_tool if previous else None),
        previous_tool_result=(
            tool_result
            if tool_result is not None
            else (previous.previous_tool_result if previous else None)
        ),
        response_strategy=_strategy(intent, message),
        confidence=confidence,
        task_status="completed" if tool_name and tool_result is not None else "active",
        predicted_next_action=next_action,
        prediction_confidence=confidence if next_action != "CONTINUE_CONTEXT" else min(confidence, 0.85),
        missing_information=missing,
    )


def load_conversation_state(messages: list[Any]) -> Optional[ConversationState]:
    for message in reversed(messages):
        raw = getattr(message, "entities_json", None)
        if not raw:
            continue
        try:
            data = __import__("json").loads(raw)
            state = data.get("conversation_state")
            if state:
                return ConversationState.model_validate(state)
        except (TypeError, ValueError):
            continue
    return None


def state_prompt(state: Optional[ConversationState]) -> str:
    if not state:
        return ""
    return (
        "Short-term conversation state (use only when relevant; do not expose it):\n"
        f"- topic: {state.current_topic or 'none'}\n"
        f"- goal: {state.user_goal or 'none'}\n"
        f"- intent: {state.current_intent}\n"
        f"- references: {', '.join(state.unresolved_references) or 'none'}\n"
        f"- resolved reference topic: {state.current_topic or 'none'}\n"
        f"- response strategy: {state.response_strategy}\n"
    )
