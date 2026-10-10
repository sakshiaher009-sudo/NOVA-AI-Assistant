"""Tests for nova.interfaces — typed dataclasses and enums."""

from nova.interfaces import (
    AudioResponse,
    AudioSegment,
    ExecutionPlan,
    Intent,
    IntentCategory,
    NovaResponse,
    PlanStep,
    ToolParameter,
    ToolResult,
    ToolSchema,
    Transcript,
    VADEvent,
    ValidationResult,
    ValidationStatus,
    VerificationResult,
)


class TestEnums:
    """Enum values and membership."""

    def test_validation_status_values(self):
        assert ValidationStatus.CLEAR.value == "CLEAR"
        assert ValidationStatus.UNCLEAR.value == "UNCLEAR"

    def test_intent_category_values(self):
        assert IntentCategory.CHAT.value == "CHAT"
        assert IntentCategory.QUESTION.value == "QUESTION"
        assert IntentCategory.COMMAND.value == "COMMAND"

    def test_enum_from_string(self):
        assert ValidationStatus("CLEAR") is ValidationStatus.CLEAR
        assert IntentCategory("COMMAND") is IntentCategory.COMMAND


class TestVADEvent:
    def test_creation(self):
        event = VADEvent(start_ms=100, end_ms=500, confidence=0.9)
        assert event.start_ms == 100
        assert event.end_ms == 500
        assert event.confidence == 0.9

    def test_default_confidence(self):
        event = VADEvent(start_ms=0, end_ms=1000)
        assert event.confidence == 1.0

    def test_frozen(self):
        event = VADEvent(start_ms=0, end_ms=100)
        try:
            event.start_ms = 50  # type: ignore
            assert False, "Should have raised"
        except AttributeError:
            pass


class TestAudioSegment:
    def test_creation(self):
        seg = AudioSegment(audio_bytes=b"\x00" * 100, sample_rate=16000)
        assert len(seg.audio_bytes) == 100
        assert seg.sample_rate == 16000
        assert seg.channels == 1

    def test_defaults(self):
        seg = AudioSegment(audio_bytes=b"")
        assert seg.sample_rate == 16000
        assert seg.channels == 1
        assert seg.start_ms == 0
        assert seg.end_ms == 0


class TestTranscript:
    def test_creation(self):
        t = Transcript(text="Hello world", language="en", confidence=0.95)
        assert t.text == "Hello world"
        assert t.confidence == 0.95

    def test_defaults(self):
        t = Transcript(text="test")
        assert t.language == "en"
        assert t.confidence is None
        assert t.duration_ms == 0


class TestValidationResult:
    def test_clear(self):
        v = ValidationResult(status=ValidationStatus.CLEAR)
        assert v.is_clear is True
        assert v.reason is None

    def test_unclear(self):
        v = ValidationResult(status=ValidationStatus.UNCLEAR, reason="too short")
        assert v.is_clear is False
        assert v.reason == "too short"


class TestIntent:
    def test_creation(self):
        intent = Intent(
            category=IntentCategory.COMMAND,
            confidence=0.85,
            raw_text="open chrome",
        )
        assert intent.category == IntentCategory.COMMAND
        assert intent.confidence == 0.85
        assert intent.raw_text == "open chrome"


class TestPlanStep:
    def test_creation(self):
        step = PlanStep(
            tool_name="calculator",
            arguments={"expression": "2+2"},
            description="Calculate 2+2",
        )
        assert step.tool_name == "calculator"
        assert step.arguments == {"expression": "2+2"}

    def test_defaults(self):
        step = PlanStep(tool_name="test")
        assert step.arguments == {}
        assert step.expected_type is None
        assert step.description == ""


class TestExecutionPlan:
    def test_empty_plan(self):
        plan = ExecutionPlan()
        assert plan.steps == []
        assert plan.original_command == ""

    def test_with_steps(self):
        plan = ExecutionPlan(
            steps=[PlanStep(tool_name="a"), PlanStep(tool_name="b")],
            original_command="do something",
        )
        assert len(plan.steps) == 2


class TestToolResult:
    def test_success(self):
        r = ToolResult(success=True, result="42", display_text="The answer is 42")
        assert r.success is True
        assert r.result == "42"

    def test_failure(self):
        r = ToolResult(success=False, error="Division by zero")
        assert r.success is False
        assert r.error == "Division by zero"

    def test_defaults(self):
        r = ToolResult()
        assert r.success is True
        assert r.result is None


class TestVerificationResult:
    def test_passed(self):
        v = VerificationResult(passed=True, details="OK")
        assert v.passed is True

    def test_failed(self):
        v = VerificationResult(passed=False, details="Type mismatch")
        assert v.passed is False


class TestNovaResponse:
    def test_creation(self):
        r = NovaResponse(
            text="Hello!",
            success=True,
            intent_category=IntentCategory.CHAT,
        )
        assert r.text == "Hello!"
        assert r.success is True
        assert r.intent_category == IntentCategory.CHAT

    def test_error_response(self):
        r = NovaResponse(text="Error occurred", success=False, error="timeout")
        assert r.success is False
        assert r.error == "timeout"


class TestAudioResponse:
    def test_creation(self):
        r = AudioResponse(audio_path="/tmp/test.wav", text="Hello")
        assert r.audio_path == "/tmp/test.wav"
        assert r.audio_format == "wav"
        assert r.sample_rate == 22050


class TestToolSchema:
    def test_creation(self):
        schema = ToolSchema(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(
                    name="input",
                    type="string",
                    description="The input",
                    required=True,
                ),
            ],
        )
        assert schema.name == "test_tool"
        assert len(schema.parameters) == 1
        assert schema.parameters[0].required is True
