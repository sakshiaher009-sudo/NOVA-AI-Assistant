"""Nova Pipeline — LLM-based Intent Detection.

Classifies a CLEAR transcript into exactly one of:
  - ``CHAT``     — casual conversation
  - ``QUESTION`` — information-seeking query
  - ``COMMAND``  — actionable instruction (trigger tools)

Uses a structured JSON prompt to Ollama.
"""

from __future__ import annotations

import json

import structlog

from nova.config import NovaConfig, get_config
from nova.interfaces import Intent, IntentCategory
from nova import llm_client

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

INTENT_PROMPT_TEMPLATE = """\
You are an intent classifier for a voice assistant called Nova.

Classify the following user utterance into EXACTLY ONE category:

- CHAT: Casual conversation, greetings, small talk, or opinions.
  Examples: "Hello", "How are you?", "Tell me a joke", "Good morning"

- QUESTION: Information-seeking queries that need a factual or explanatory answer.
  Examples: "What is machine learning?", "Who won the World Cup?", "Explain quantum computing"

- COMMAND: Actionable instructions that require executing a task or tool.
  Examples: "Open Chrome", "Set a reminder for 5 PM", "Calculate 42 * 17", "Search for Python tutorials", "Create a note about groceries"

User utterance: "{text}"

Respond with ONLY a JSON object in this exact format (no markdown, no extra text):
{{"intent": "CHAT|QUESTION|COMMAND", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def classify_intent(
    text: str,
    *,
    config: NovaConfig | None = None,
) -> Intent:
    """Classify a transcript into CHAT, QUESTION, or COMMAND.

    Args:
        text: The clear transcript text to classify.
        config: Optional config override.

    Returns:
        An ``Intent`` with category, confidence, and the original text.
    """
    cfg = config or get_config()
    prompt = INTENT_PROMPT_TEMPLATE.format(text=text)

    try:
        raw = await llm_client.generate(
            prompt,
            temperature=0.1,  # low temp for deterministic classification
            format="json",
            config=cfg,
        )

        intent = _parse_intent_response(raw, text)
        logger.debug(
            "nova_intent_classified",
            category=intent.category.value,
            confidence=intent.confidence,
            text_preview=text[:80],
        )
        return intent

    except Exception as exc:
        logger.warning("nova_intent_classification_failed", error=str(exc))
        # Fallback to CHAT with low confidence
        return Intent(
            category=IntentCategory.CHAT,
            confidence=0.3,
            raw_text=text,
        )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_intent_response(raw: str, original_text: str) -> Intent:
    """Parse the LLM's JSON response into an Intent object.

    Falls back to CHAT with low confidence on any parse failure.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        import re
        match = re.search(r"\{[^}]+\}", raw)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return _fallback_intent(original_text, "JSON parse failed")
        else:
            return _fallback_intent(original_text, "No JSON found in response")

    # Extract intent category
    intent_str = data.get("intent", "").upper().strip()
    try:
        category = IntentCategory(intent_str)
    except ValueError:
        return _fallback_intent(original_text, f"Unknown intent: {intent_str}")

    # Extract confidence
    try:
        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.5

    return Intent(
        category=category,
        confidence=confidence,
        raw_text=original_text,
    )


def _fallback_intent(text: str, reason: str) -> Intent:
    """Return a safe CHAT fallback when classification fails."""
    logger.warning("nova_intent_fallback", reason=reason)
    return Intent(
        category=IntentCategory.CHAT,
        confidence=0.3,
        raw_text=text,
    )
