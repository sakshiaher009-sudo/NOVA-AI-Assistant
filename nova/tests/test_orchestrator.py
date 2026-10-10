"""Tests for nova.orchestrator — end-to-end pipeline with mocked deps."""

import json
from typing import Any
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from nova.config import NovaConfig
from nova.interfaces import IntentCategory, NovaResponse, ToolResult
from nova.orchestrator import NovaPipeline
from nova.tools.base_tool import NovaTool


# ---------------------------------------------------------------------------
# Test tool
# ---------------------------------------------------------------------------

class EchoTool(NovaTool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes back the input"

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        text = params.get("text", "")
        return ToolResult(success=True, result=text, display_text=f"Echo: {text}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNovaPipelineInit:
    def test_default_init(self):
        pipeline = NovaPipeline()
        assert pipeline.config is not None
        assert len(pipeline.registry) == 0

    def test_init_with_tools(self):
        pipeline = NovaPipeline(tools=[EchoTool()])
        assert len(pipeline.registry) == 1
        assert "echo" in pipeline.registry

    def test_register_tool(self):
        pipeline = NovaPipeline()
        pipeline.register_tool(EchoTool())
        assert "echo" in pipeline.registry


@pytest.mark.asyncio
class TestRunText:
    """Test the text-only pipeline path."""

    async def test_unclear_text(self):
        pipeline = NovaPipeline()
        response = await pipeline.run_text("")  # Empty = UNCLEAR
        assert isinstance(response, NovaResponse)
        assert response.intent_category is None  # UNCLEAR path

    async def test_chat_path(self):
        """CLEAR text classified as CHAT → LLM response."""
        intent_json = json.dumps({"intent": "CHAT", "confidence": 0.9})
        with patch("nova.intent.llm_client.generate", new_callable=AsyncMock, return_value=intent_json):
            mock_llm_response = MagicMock()
            mock_llm_response.content = "Hello! I'm Nova."
            with patch("nova.llm_client.chat", new_callable=AsyncMock, return_value=mock_llm_response):
                pipeline = NovaPipeline()
                response = await pipeline.run_text("Hello there")
                assert response.success is True
                assert response.intent_category == IntentCategory.CHAT
                assert "Nova" in response.text

    async def test_command_no_tools(self):
        """COMMAND intent but no tools registered → error."""
        intent_json = json.dumps({"intent": "COMMAND", "confidence": 0.95})
        with patch("nova.intent.llm_client.generate", new_callable=AsyncMock, return_value=intent_json):
            pipeline = NovaPipeline()  # No tools
            response = await pipeline.run_text("Open Chrome")
            assert response.success is False
            assert "No tools" in response.text or "error" in response.text.lower()

    async def test_command_with_tool(self):
        """COMMAND intent with a matching tool → plan + execute."""
        from nova.interfaces import Intent, ExecutionPlan, PlanStep

        mock_intent = Intent(
            category=IntentCategory.COMMAND,
            confidence=0.95,
            raw_text="Echo hello",
        )
        mock_plan = ExecutionPlan(
            steps=[PlanStep(tool_name="echo", arguments={"text": "hello"}, description="Echo")],
            original_command="Echo hello",
            reasoning="Echo the text",
        )
        with patch("nova.intent.classify_intent", new_callable=AsyncMock, return_value=mock_intent):
            with patch("nova.planner.create_plan", new_callable=AsyncMock, return_value=mock_plan):
                pipeline = NovaPipeline(tools=[EchoTool()])
                response = await pipeline.run_text("Echo hello")
                assert response.success is True
                assert response.intent_category == IntentCategory.COMMAND
                assert "Echo" in response.text

