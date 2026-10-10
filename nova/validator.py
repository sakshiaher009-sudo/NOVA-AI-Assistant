"""Nova Pipeline — Transcript Validator.

Given a ``Transcript``, decides whether it is CLEAR (proceed to intent
detection) or UNCLEAR (short-circuit to an "ask user to repeat" response).

Pure functions — no I/O, no LLM calls, trivially testable.
"""

from __future__ import annotations

import re

import structlog

from nova.config import NovaConfig, get_config
from nova.interfaces import Transcript, ValidationResult, ValidationStatus

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Known hallucination patterns from Whisper
# ---------------------------------------------------------------------------

_HALLUCINATION_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(thank(s| you)( for watching| for listening)?[.!]?\s*)+$", re.I),
    re.compile(r"^(please subscribe[.!]?\s*)+$", re.I),
    re.compile(r"^(music|applause|laughter)\s*$", re.I),
    re.compile(r"^\[.*\]\s*$"),  # [Music], [Applause], etc.
    re.compile(r"^\.+$"),  # Just dots
    re.compile(r"^(.)\1{4,}$"),  # Repeated single character ≥5 times
    re.compile(r"^(you|the|i|a|is)\s*$", re.I),  # Single common word
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate(
    transcript: Transcript,
    *,
    config: NovaConfig | None = None,
) -> ValidationResult:
    """Validate a transcript and decide CLEAR or UNCLEAR.

    Checks (in order):
      1. Empty or whitespace-only text.
      2. Text shorter than ``min_length`` characters.
      3. Confidence below ``min_confidence`` (if confidence is available).
      4. Known Whisper hallucination patterns.

    Args:
        transcript: The transcript to validate.
        config: Optional config override.

    Returns:
        A ``ValidationResult`` with status and optional reason.
    """
    cfg = config or get_config()
    text = transcript.text.strip()

    # 1. Empty text
    if not text:
        reason = "No speech detected — the transcript is empty."
        logger.debug("nova_validation_unclear", reason=reason)
        return ValidationResult(status=ValidationStatus.UNCLEAR, reason=reason)

    # 2. Too short
    if len(text) < cfg.validator_min_length:
        reason = (
            f"Transcript too short ({len(text)} chars, "
            f"minimum {cfg.validator_min_length})."
        )
        logger.debug("nova_validation_unclear", reason=reason)
        return ValidationResult(status=ValidationStatus.UNCLEAR, reason=reason)

    # 3. Low confidence
    if (
        transcript.confidence is not None
        and transcript.confidence < cfg.validator_min_confidence
    ):
        reason = (
            f"Low transcription confidence ({transcript.confidence:.2f}, "
            f"minimum {cfg.validator_min_confidence:.2f})."
        )
        logger.debug("nova_validation_unclear", reason=reason)
        return ValidationResult(status=ValidationStatus.UNCLEAR, reason=reason)

    # 4. Hallucination patterns
    for pattern in _HALLUCINATION_PATTERNS:
        if pattern.match(text):
            reason = f"Detected likely hallucination: \"{text}\""
            logger.debug("nova_validation_unclear", reason=reason)
            return ValidationResult(status=ValidationStatus.UNCLEAR, reason=reason)

    # All checks passed
    logger.debug("nova_validation_clear", text_len=len(text))
    return ValidationResult(status=ValidationStatus.CLEAR)
