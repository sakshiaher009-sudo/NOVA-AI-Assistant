"""Tests for nova.intent — LLM-based intent classification."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from nova.interfaces import IntentCategory
from nova.intent import classify_intent, _parse_intent_response


class TestParseIntentResponse:
    """Test the JSON response parser (no LLM needed)."""

    def test_valid_chat(self):
        raw = json.dumps({"intent": "CHAT", "confidence": 0.9, "reasoning": "greeting"})
        intent = _parse_intent_response(raw, "hello")
        assert intent.category == IntentCategory.CHAT
        assert intent.confidence == 0.9

    def test_valid_question(self):
        raw = json.dumps({"intent": "QUESTION", "confidence": 0.85})
        intent = _parse_intent_response(raw, "what is AI?")
        assert intent.category == IntentCategory.QUESTION

    def test_valid_command(self):
        raw = json.dumps({"intent": "COMMAND", "confidence": 0.95})
        intent = _parse_intent_response(raw, "open chrome")
        assert intent.category == IntentCategory.COMMAND

    def test_lowercase_intent(self):
        raw = json.dumps({"intent": "chat", "confidence": 0.8})
        intent = _parse_intent_response(raw, "hey")
        assert intent.category == IntentCategory.CHAT

    def test_invalid_json(self):
        intent = _parse_intent_response("not json at all", "test")
        assert intent.category == IntentCategory.CHAT
        assert intent.confidence == 0.3  # fallback

    def test_json_in_markdown_block(self):
        raw = '```json\n{"intent": "COMMAND", "confidence": 0.9}\n```'
        intent = _parse_intent_response(raw, "do something")
        assert intent.category == IntentCategory.COMMAND

    def test_unknown_intent_string(self):
        raw = json.dumps({"intent": "FOOBAR", "confidence": 0.9})
        intent = _parse_intent_response(raw, "test")
        assert intent.category == IntentCategory.CHAT  # fallback
        assert intent.confidence == 0.3

    def test_missing_confidence(self):
        raw = json.dumps({"intent": "QUESTION"})
        intent = _parse_intent_response(raw, "what?")
        assert intent.category == IntentCategory.QUESTION
        assert intent.confidence == 0.5  # default

    def test_confidence_clamped_above_1(self):
        raw = json.dumps({"intent": "CHAT", "confidence": 5.0})
        intent = _parse_intent_response(raw, "hi")
        assert intent.confidence == 1.0

    def test_confidence_clamped_below_0(self):
        raw = json.dumps({"intent": "CHAT", "confidence": -0.5})
        intent = _parse_intent_response(raw, "hi")
        assert intent.confidence == 0.0


@pytest.mark.asyncio
class TestClassifyIntent:
    """Test the full classify_intent function with mocked LLM."""

    async def test_classify_chat(self):
        mock_response = json.dumps({"intent": "CHAT", "confidence": 0.9})
        with patch("nova.intent.llm_client.generate", new_callable=AsyncMock, return_value=mock_response):
            intent = await classify_intent("Hello there!")
            assert intent.category == IntentCategory.CHAT
            assert intent.raw_text == "Hello there!"

    async def test_classify_command(self):
        mock_response = json.dumps({"intent": "COMMAND", "confidence": 0.95})
        with patch("nova.intent.llm_client.generate", new_callable=AsyncMock, return_value=mock_response):
            intent = await classify_intent("Open Chrome browser")
            assert intent.category == IntentCategory.COMMAND

    async def test_llm_failure_fallback(self):
        with patch("nova.intent.llm_client.generate", new_callable=AsyncMock, side_effect=ConnectionError("timeout")):
            intent = await classify_intent("test input")
            assert intent.category == IntentCategory.CHAT
            assert intent.confidence == 0.3
