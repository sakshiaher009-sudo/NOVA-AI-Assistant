"""Tests for nova.executor — plan step dispatching."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from nova.interfaces import ExecutionPlan, PlanStep, ToolResult
from nova.executor import execute_plan
from nova.tools.base_tool import NovaTool
from nova.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeSuccessTool(NovaTool):
    @property
    def name(self) -> str:
        return "success_tool"

    @property
    def description(self) -> str:
        return "Always succeeds"

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, result="ok", display_text="Done")


class FakeFailTool(NovaTool):
    @property
    def name(self) -> str:
        return "fail_tool"

    @property
    def description(self) -> str:
        return "Always fails"

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        return ToolResult(success=False, error="Intentional failure")


def _registry(*tools: NovaTool) -> ToolRegistry:
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    return reg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestExecutePlan:

    async def test_empty_plan(self):
        plan = ExecutionPlan(steps=[], original_command="nothing")
        results = await execute_plan(plan, _registry())
        assert len(results) == 1
        assert not results[0].success

    async def test_single_success(self):
        plan = ExecutionPlan(
            steps=[PlanStep(tool_name="success_tool")],
            original_command="do it",
        )
        results = await execute_plan(plan, _registry(FakeSuccessTool()))
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].result == "ok"

    async def test_multiple_steps_all_succeed(self):
        plan = ExecutionPlan(
            steps=[
                PlanStep(tool_name="success_tool"),
                PlanStep(tool_name="success_tool"),
            ],
            original_command="do two things",
        )
        results = await execute_plan(plan, _registry(FakeSuccessTool()))
        assert len(results) == 2
        assert all(r.success for r in results)

    async def test_fail_fast_stops_on_failure(self):
        plan = ExecutionPlan(
            steps=[
                PlanStep(tool_name="fail_tool"),
                PlanStep(tool_name="success_tool"),
            ],
            original_command="do both",
        )
        reg = _registry(FakeFailTool(), FakeSuccessTool())
        results = await execute_plan(plan, reg, fail_fast=True)
        assert len(results) == 1  # Stopped after first failure
        assert not results[0].success

    async def test_continue_on_error(self):
        plan = ExecutionPlan(
            steps=[
                PlanStep(tool_name="fail_tool"),
                PlanStep(tool_name="success_tool"),
            ],
            original_command="do both",
        )
        reg = _registry(FakeFailTool(), FakeSuccessTool())
        results = await execute_plan(plan, reg, fail_fast=False)
        assert len(results) == 2
        assert not results[0].success
        assert results[1].success

    async def test_unknown_tool(self):
        plan = ExecutionPlan(
            steps=[PlanStep(tool_name="nonexistent")],
            original_command="use unknown",
        )
        results = await execute_plan(plan, _registry())
        assert len(results) == 1
        assert not results[0].success
        assert "not found" in results[0].error.lower()
