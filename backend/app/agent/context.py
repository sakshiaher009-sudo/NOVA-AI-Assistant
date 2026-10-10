"""NOVA — Conversation Context Builder."""

from __future__ import annotations

from app.config import get_settings
from app.llm.schemas import LLMMessage
from app.agent.prompts import get_system_prompt
from app.agent.conversation_state import ConversationState, state_prompt


def summarize_older_messages(messages: list[dict]) -> str:
    """Create a compact summary of older turns to preserve context without exceeding token window."""
    lines = []
    # Take up to the 10 most recent of the overflow messages
    overflow = messages[-10:] if len(messages) > 10 else messages
    for m in overflow:
        role = "User" if m.get("role") == "user" else "Assistant"
        content = (m.get("content") or "").strip().replace("\n", " ")
        if len(content) > 90:
            content = content[:87] + "..."
        if content:
            lines.append(f"- {role}: {content}")
    return "\n".join(lines)


def _relevant_messages(
    messages: list[dict],
    current_message: str,
    state: ConversationState | None,
    limit: int,
) -> list[dict]:
    """Keep the recent exchange and older turns related to the current topic."""
    if len(messages) <= limit:
        return messages
    recent_count = min(8, limit)
    recent = messages[-recent_count:]
    topic = state.current_topic if state else ""
    terms = {
        term.lower().strip(".,?!")
        for term in f"{current_message} {topic}".split()
        if len(term.strip(".,?!")) >= 4
    }
    older = messages[:-recent_count]
    related = [
        msg for msg in older
        if terms and any(term in (msg.get("content") or "").lower() for term in terms)
    ]
    return (related[-(limit - recent_count):] + recent)[-limit:]


def build_context(
    conversation_messages: list[dict],
    system_prompt: str | None = None,
    max_messages: int | None = None,
    conversation_state: ConversationState | None = None,
    current_message: str | None = None,
    relevant_memory: list[dict] | None = None,
    relevant_tool_result: str | None = None,
    include_tools: bool = True,
) -> list[LLMMessage]:
    """
    Build the LLM message context from conversation history.

    Uses a sliding window to limit context size and summarizes older turns.
    """
    settings = get_settings()
    max_msgs = max_messages or settings.max_conversation_context

    messages: list[LLMMessage] = []

    # System prompt always first
    messages.append(
        LLMMessage(
            role="system",
            content=system_prompt or get_system_prompt(include_tools=include_tools),
        )
    )
    if conversation_state:
        messages.append(LLMMessage(role="system", content=state_prompt(conversation_state)))
    if relevant_memory:
        memory_text = "\n".join(
            f"- {item.get('content', '')}" for item in relevant_memory[:3] if item.get("content")
        )
        if memory_text:
            messages.append(
                LLMMessage(
                    role="system",
                    content=f"Relevant saved user context (use only if it helps):\n{memory_text}",
                )
            )
    if relevant_tool_result:
        messages.append(
            LLMMessage(
                role="system",
                content=f"Relevant result from the immediately preceding action:\n{relevant_tool_result}",
            )
        )

    # Summarize older turns if window is exceeded
    selected = _relevant_messages(
        conversation_messages,
        current_message or "",
        conversation_state,
        max_msgs,
    )
    recent = selected
    if len(selected) < len(conversation_messages):
        older = conversation_messages[:-len(selected)]
        summary_source = older
        if current_message or conversation_state:
            terms = {
                term.lower().strip(".,?!")
                for term in f"{current_message or ''} "
                f"{conversation_state.current_topic if conversation_state else ''}".split()
                if len(term.strip(".,?!")) >= 4
            }
            summary_source = [
                msg for msg in older
                if terms and any(term in (msg.get("content") or "").lower() for term in terms)
            ]
        summary = summarize_older_messages(summary_source)
        if summary:
            messages.append(
                LLMMessage(
                    role="system",
                    content=f"Earlier conversation context summary:\n{summary}",
                )
            )
    for msg in recent:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant", "system") and content:
            messages.append(LLMMessage(role=role, content=content))

    return messages
