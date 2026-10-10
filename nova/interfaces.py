"""Nova Pipeline — Typed Interfaces.

All data structures exchanged between pipeline stages are defined here.
Modules communicate via these well-defined objects — never raw dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ValidationStatus(str, Enum):
    """Transcript validation outcome."""
    CLEAR = "CLEAR"
    UNCLEAR = "UNCLEAR"


class IntentCategory(str, Enum):
    """Classified intent categories."""
    CHAT = "CHAT"
    QUESTION = "QUESTION"
    COMMAND = "COMMAND"


# ---------------------------------------------------------------------------
# VAD
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VADEvent:
    """A detected speech region within the audio stream.

    Attributes:
        start_ms: Start of speech in milliseconds from audio beginning.
        end_ms: End of speech in milliseconds from audio beginning.
        confidence: Average speech probability for this segment (0.0–1.0).
    """
    start_ms: int
    end_ms: int
    confidence: float = 1.0


@dataclass(frozen=True)
class AudioSegment:
    """Raw audio data for a single speech segment.

    Attributes:
        audio_bytes: Raw PCM audio data (16-bit signed LE).
        sample_rate: Sample rate in Hz (typically 16000).
        channels: Number of audio channels (typically 1 = mono).
        start_ms: Offset from the start of the original stream.
        end_ms: End offset from the start of the original stream.
    """
    audio_bytes: bytes
    sample_rate: int = 16000
    channels: int = 1
    start_ms: int = 0
    end_ms: int = 0


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Transcript:
    """Result of speech-to-text transcription.

    Attributes:
        text: Transcribed text content.
        language: Detected or forced language code.
        confidence: Average log-probability confidence (higher = better).
                    None if the engine doesn't provide confidence.
        duration_ms: Wall-clock time spent on transcription.
    """
    text: str
    language: str = "en"
    confidence: Optional[float] = None
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationResult:
    """Outcome of transcript validation.

    Attributes:
        status: CLEAR (proceed) or UNCLEAR (ask user to repeat).
        reason: Human-readable reason when status is UNCLEAR.
    """
    status: ValidationStatus
    reason: Optional[str] = None

    @property
    def is_clear(self) -> bool:
        return self.status == ValidationStatus.CLEAR


# ---------------------------------------------------------------------------
# Intent Detection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Intent:
    """Classified user intent.

    Attributes:
        category: One of CHAT, QUESTION, or COMMAND.
        confidence: Classification confidence (0.0–1.0).
        raw_text: The original transcript text that was classified.
    """
    category: IntentCategory
    confidence: float
    raw_text: str


# ---------------------------------------------------------------------------
# Planning & Execution
# ---------------------------------------------------------------------------

@dataclass
class ToolParameter:
    """Schema description of a single tool parameter."""
    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Optional[Any] = None


@dataclass
class ToolSchema:
    """Schema describing a tool's interface for the LLM."""
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)


@dataclass
class PlanStep:
    """A single step in an execution plan.

    Attributes:
        tool_name: Name of the tool to invoke.
        arguments: Keyword arguments to pass to the tool.
        expected_type: Optional expected return type (for verification).
        description: Human-readable description of what this step does.
    """
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    expected_type: Optional[str] = None
    description: str = ""


@dataclass
class ExecutionPlan:
    """An ordered list of tool calls derived from a COMMAND intent.

    Attributes:
        steps: Ordered list of PlanStep items.
        original_command: The raw command text from the user.
        reasoning: LLM's reasoning for the chosen plan.
    """
    steps: list[PlanStep] = field(default_factory=list)
    original_command: str = ""
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Tool Results
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Result from executing a single tool.

    Attributes:
        success: Whether the tool execution succeeded.
        result: The tool's return value (any serializable type).
        error: Error message if success is False.
        display_text: Human-readable summary of the result.
    """
    success: bool = True
    result: Any = None
    error: Optional[str] = None
    display_text: Optional[str] = None


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VerificationResult:
    """Post-execution verification outcome.

    Attributes:
        passed: Whether the tool result matches the planned intent.
        details: Explanation of the verification outcome.
    """
    passed: bool
    details: str = ""


# ---------------------------------------------------------------------------
# Final Response
# ---------------------------------------------------------------------------

@dataclass
class NovaResponse:
    """Unified pipeline response object.

    Every pipeline path (CHAT, QUESTION, COMMAND, UNCLEAR) produces one of
    these before being sent to TTS.

    Attributes:
        text: The final response text to speak / display.
        success: Overall success flag.
        intent_category: Which intent path produced this response.
        structured_data: Optional machine-readable data (tool results, etc.).
        error: Error message if success is False.
    """
    text: str
    success: bool = True
    intent_category: Optional[IntentCategory] = None
    structured_data: Optional[dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class AudioResponse:
    """Final audio output from the pipeline.

    Attributes:
        audio_path: Path to the generated audio file.
        audio_format: Audio file format (e.g., 'wav', 'aiff').
        sample_rate: Sample rate of the output audio.
        text: The text that was synthesized (for debugging).
        nova_response: The full NovaResponse object.
    """
    audio_path: str
    audio_format: str = "wav"
    sample_rate: int = 22050
    text: str = ""
    nova_response: Optional[NovaResponse] = None
