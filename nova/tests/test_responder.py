"""Tests for nova.responder — response building for all pipeline paths."""

from nova.interfaces import (
    Intent,
    IntentCategory,
    NovaResponse,
    ToolResult,
    ValidationResult,
    ValidationStatus,
    VerificationResult,
)
from nova.responder import (
    build_chat_response,
    build_command_response,
    build_error_response,
    build_unclear_response,
)


class TestBuildUnclearResponse:
    def test_returns_nova_response(self):
        v = ValidationResult(status=ValidationStatus.UNCLEAR, reason="too short")
        response = build_unclear_response(v)
        assert isinstance(response, NovaResponse)
        assert response.success is True  # Pipeline worked, just needs clarification
        assert response.intent_category is None

    def test_has_clarification_text(self):
        v = ValidationResult(status=ValidationStatus.UNCLEAR, reason="empty")
        response = build_unclear_response(v)
        assert len(response.text) > 0
        # Should contain some form of "repeat" or "try again"
        lower = response.text.lower()
        assert any(w in lower for w in ("repeat", "try again", "understand", "catch"))

    def test_includes_reason_in_structured_data(self):
        v = ValidationResult(status=ValidationStatus.UNCLEAR, reason="low confidence")
        response = build_unclear_response(v)
        assert response.structured_data is not None
        assert response.structured_data["validation_reason"] == "low confidence"


class TestBuildChatResponse:
    def test_chat_response(self):
        intent = Intent(category=IntentCategory.CHAT, confidence=0.9, raw_text="hi")
        response = build_chat_response(intent, "Hello! How can I help?")
        assert response.text == "Hello! How can I help?"
        assert response.success is True
        assert response.intent_category == IntentCategory.CHAT

    def test_question_response(self):
        intent = Intent(category=IntentCategory.QUESTION, confidence=0.85, raw_text="what is AI?")
        response = build_chat_response(intent, "AI is artificial intelligence.")
        assert response.intent_category == IntentCategory.QUESTION
        assert "artificial intelligence" in response.text


class TestBuildCommandResponse:
    def test_all_success(self):
        intent = Intent(category=IntentCategory.COMMAND, confidence=0.9, raw_text="calc")
        results = [ToolResult(success=True, result="42", display_text="The answer is 42")]
        verifications = [VerificationResult(passed=True)]
        response = build_command_response(intent, results, verifications)
        assert response.success is True
        assert "42" in response.text
        assert response.intent_category == IntentCategory.COMMAND

    def test_all_failed(self):
        intent = Intent(category=IntentCategory.COMMAND, confidence=0.9, raw_text="fail")
        results = [ToolResult(success=False, error="Division by zero")]
        verifications = [VerificationResult(passed=False)]
        response = build_command_response(intent, results, verifications)
        assert response.success is False
        assert "Division by zero" in response.text

    def test_partial_success(self):
        intent = Intent(category=IntentCategory.COMMAND, confidence=0.9, raw_text="multi")
        results = [
            ToolResult(success=True, result="ok", display_text="Step 1 done"),
            ToolResult(success=False, error="Step 2 failed"),
        ]
        verifications = [
            VerificationResult(passed=True),
            VerificationResult(passed=False),
        ]
        response = build_command_response(intent, results, verifications)
        assert response.success is False  # Not all verified
        assert "1 step(s) succeeded" in response.text

    def test_structured_data_present(self):
        intent = Intent(category=IntentCategory.COMMAND, confidence=0.9, raw_text="test")
        results = [ToolResult(success=True, result="x", display_text="Done")]
        verifications = [VerificationResult(passed=True)]
        response = build_command_response(intent, results, verifications)
        assert response.structured_data is not None
        assert "tool_results" in response.structured_data


class TestBuildErrorResponse:
    def test_error(self):
        response = build_error_response("Something broke")
        assert response.success is False
        assert "Something broke" in response.text
        assert response.error == "Something broke"
