"""Nova Pipeline — Response Builder.

Unifies all pipeline paths (CHAT, QUESTION, COMMAND, UNCLEAR) into a
single ``NovaResponse`` object with a consistent shape.
"""

from __future__ import annotations

from typing import Optional

import structlog

from nova.interfaces import (
    Intent,
    IntentCategory,
    NovaResponse,
    ToolResult,
    ValidationResult,
    ValidationStatus,
    VerificationResult,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Clarification messages for UNCLEAR transcripts
# ---------------------------------------------------------------------------

UNCLEAR_RESPONSES = [
    "I didn't quite catch that. Could you please repeat?",
    "Sorry, I couldn't understand what you said. Can you try again?",
    "I'm having trouble understanding. Could you speak a little more clearly?",
]

_unclear_index = 0


def _get_unclear_message(reason: str | None = None) -> str:
    """Return a clarification message, cycling through variants."""
    global _unclear_index
    msg = UNCLEAR_RESPONSES[_unclear_index % len(UNCLEAR_RESPONSES)]
    _unclear_index += 1
    return msg


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_unclear_response(validation: ValidationResult) -> NovaResponse:
    """Build a response for UNCLEAR transcripts (short-circuit path).

    Args:
        validation: The validation result with reason.

    Returns:
        A ``NovaResponse`` prompting the user to repeat.
    """
    text = _get_unclear_message(validation.reason)
    logger.debug("nova_response_unclear", reason=validation.reason)
    return NovaResponse(
        text=text,
        success=True,  # The pipeline succeeded — just needs clarification
        intent_category=None,
        structured_data={"validation_reason": validation.reason},
    )


def build_chat_response(
    intent: Intent,
    llm_text: str,
) -> NovaResponse:
    """Build a response for CHAT or QUESTION intents.

    Args:
        intent: The classified intent.
        llm_text: The LLM's conversational reply.

    Returns:
        A ``NovaResponse`` with the LLM's answer.
    """
    logger.debug(
        "nova_response_chat",
        category=intent.category.value,
        text_len=len(llm_text),
    )
    return NovaResponse(
        text=llm_text,
        success=True,
        intent_category=intent.category,
    )


def build_command_response(
    intent: Intent,
    tool_results: list[ToolResult],
    verifications: list[VerificationResult],
) -> NovaResponse:
    """Build a response for COMMAND intents after tool execution.

    Args:
        intent: The classified intent.
        tool_results: Results from each executed tool step.
        verifications: Verification outcomes for each tool result.

    Returns:
        A ``NovaResponse`` summarizing the command execution.
    """
    all_passed = all(v.passed for v in verifications)
    any_success = any(r.success for r in tool_results)

    # Build structured data from tool results
    structured: dict = {
        "tool_results": [
            {
                "success": r.success,
                "display_text": r.display_text,
                "error": r.error,
            }
            for r in tool_results
        ],
        "all_verified": all_passed,
    }

    # Build the response text
    if all_passed and any_success:
        # Prefer display_text from the last successful result
        display_parts = [
            r.display_text for r in tool_results
            if r.success and r.display_text
        ]
        if display_parts:
            text = " ".join(display_parts)
        else:
            text = "Done! The command was executed successfully."
    elif any_success:
        # Partial success
        succeeded = sum(1 for r in tool_results if r.success)
        failed = sum(1 for r in tool_results if not r.success)
        text = (
            f"Partially completed: {succeeded} step(s) succeeded, "
            f"{failed} step(s) failed."
        )
        # Append first error
        first_error = next((r.error for r in tool_results if not r.success), None)
        if first_error:
            text += f" Error: {first_error}"
    else:
        # All failed
        first_error = next((r.error for r in tool_results if r.error), "Unknown error")
        text = f"Sorry, I couldn't complete that command. {first_error}"

    logger.debug(
        "nova_response_command",
        all_passed=all_passed,
        any_success=any_success,
        num_results=len(tool_results),
    )

    return NovaResponse(
        text=text,
        success=all_passed and any_success,
        intent_category=intent.category,
        structured_data=structured,
    )


def build_error_response(error: str) -> NovaResponse:
    """Build a response for pipeline-level errors.

    Args:
        error: The error message.

    Returns:
        A ``NovaResponse`` with the error details.
    """
    logger.error("nova_response_error", error=error)
    return NovaResponse(
        text=f"I encountered an error: {error}",
        success=False,
        error=error,
    )
