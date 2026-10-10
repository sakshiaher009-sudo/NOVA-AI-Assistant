"""Tests for nova.planner — command → tool-call plan."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from nova.interfaces import ToolParameter, ToolSchema
from nova.planner import create_plan, _parse_plan_response


SAMPLE_TOOLS = [
    ToolSchema(
        name="calculator",
        description="Evaluate math expressions",
        parameters=[ToolParameter(name="expression", type="string", description="Math expression")],
    ),
    ToolSchema(
        name="get_time",
        description="Get current date/time",
        parameters=[],
    ),
]

TOOL_NAMES = {t.name for t in SAMPLE_TOOLS}


class TestParsePlanResponse:
    """Test plan JSON parsing (no LLM needed)."""

    def test_valid_single_step(self):
        raw = json.dumps({
            "reasoning": "User wants calculation",
            "steps": [{"tool_name": "calculator", "arguments": {"expression": "2+2"}}],
        })
        plan = _parse_plan_response(raw, "calculate 2+2", TOOL_NAMES)
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "calculator"
        assert plan.steps[0].arguments == {"expression": "2+2"}
        assert plan.original_command == "calculate 2+2"

    def test_valid_multi_step(self):
        raw = json.dumps({
            "reasoning": "Need both",
            "steps": [
                {"tool_name": "get_time", "arguments": {}},
                {"tool_name": "calculator", "arguments": {"expression": "1+1"}},
            ],
        })
        plan = _parse_plan_response(raw, "test", TOOL_NAMES)
        assert len(plan.steps) == 2

    def test_unknown_tool_filtered(self):
        raw = json.dumps({
            "reasoning": "test",
            "steps": [
                {"tool_name": "calculator", "arguments": {}},
                {"tool_name": "nonexistent_tool", "arguments": {}},
            ],
        })
        plan = _parse_plan_response(raw, "test", TOOL_NAMES)
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "calculator"

    def test_empty_steps(self):
        raw = json.dumps({"reasoning": "No matching tool", "steps": []})
        plan = _parse_plan_response(raw, "fly to mars", TOOL_NAMES)
        assert len(plan.steps) == 0

    def test_invalid_json(self):
        plan = _parse_plan_response("not json", "test", TOOL_NAMES)
        assert len(plan.steps) == 0
        assert "Failed" in plan.reasoning or "JSON" in plan.reasoning

    def test_no_json_found(self):
        plan = _parse_plan_response("just plain text with no braces", "test", TOOL_NAMES)
        assert len(plan.steps) == 0


@pytest.mark.asyncio
class TestCreatePlan:
    """Test the full create_plan function with mocked LLM."""

    async def test_successful_plan(self):
        mock_response = json.dumps({
            "reasoning": "Calculate",
            "steps": [{"tool_name": "calculator", "arguments": {"expression": "5*5"}}],
        })
        with patch("nova.planner.llm_client.generate", new_callable=AsyncMock, return_value=mock_response):
            plan = await create_plan("calculate 5 times 5", SAMPLE_TOOLS)
            assert len(plan.steps) == 1
            assert plan.steps[0].tool_name == "calculator"

    async def test_llm_failure(self):
        with patch("nova.planner.llm_client.generate", new_callable=AsyncMock, side_effect=ConnectionError("down")):
            plan = await create_plan("test", SAMPLE_TOOLS)
            assert len(plan.steps) == 0
            assert "failed" in plan.reasoning.lower() or "Planning" in plan.reasoning
