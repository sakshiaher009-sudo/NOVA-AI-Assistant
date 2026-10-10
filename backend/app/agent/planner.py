"""Deterministic multi-step planning for NOVA's Phase 4 task execution."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import get_tool, init_tools


class PlanStep(BaseModel):
    id: int
    description: str
    tool: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None


class Plan(BaseModel):
    goal: str
    steps: list[PlanStep]
    status: str = "pending"

    def validate_plan(self) -> Optional[str]:
        if not self.goal.strip() or not self.steps:
            return "The plan must contain a goal and at least one step."
        for step in self.steps:
            tool = get_tool(step.tool)
            if not tool:
                return f"No tool is registered for planned step {step.id}: {step.tool}."
            missing = tool.validate_input(
                {key: value for key, value in step.parameters.items() if not _is_reference(value)}
            )
            if missing and not any(_is_reference(value) for value in step.parameters.values()):
                return f"Invalid parameters for step {step.id}: {missing}"
        return None


def _is_reference(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("$step.")


def _search_query(goal: str) -> str:
    lowered = goal.lower()
    if "project" in lowered or "react" in lowered or "not running" in lowered:
        return "package.json"
    match = re.search(
        r"(?:find|locate|search\s+for)\s+(?:my\s+|the\s+)?(.+?)(?:\s+(?:and|then)\s+|$)",
        goal,
        re.I,
    )
    return (match.group(1) if match else goal).strip(" .?!")


def create_plan(goal: str) -> Optional[Plan]:
    """Create a plan only for explicit multi-step inspection requests."""
    init_tools()
    if not re.search(r"\b(?:find|locate|search)\b.*\b(?:and|then)\b", goal, re.I):
        return None

    query = _search_query(goal)
    steps = [
        PlanStep(
            id=1,
            description=f"Find candidate files for {query!r}.",
            tool="file_search",
            parameters={"query": query},
        ),
        PlanStep(
            id=2,
            description="Read the selected file after candidate selection is unambiguous.",
            tool="read_file",
            parameters={"file_path": "$step.1.files[0].path"},
        ),
    ]

    lowered = goal.lower()
    if "project" in lowered or "not running" in lowered:
        steps.append(
            PlanStep(
                id=3,
                description="Check the installed Node.js version without modifying the project.",
                tool="execute_terminal",
                parameters={"command": "node --version"},
            )
        )

    plan = Plan(goal=goal, steps=steps)
    return plan if plan.validate_plan() is None else None


def plan_from_tool_calls(goal: str, tool_calls: list[dict[str, Any]]) -> Optional[Plan]:
    """Convert Ollama native tool_calls into an executable Plan."""
    if not tool_calls:
        return None
    init_tools()
    steps: list[PlanStep] = []
    for idx, tc in enumerate(tool_calls, start=1):
        fn = tc.get("function", {}) if isinstance(tc.get("function"), dict) else {}
        tool_name = fn.get("name") or tc.get("name", "")
        raw_args = fn.get("arguments", {}) if fn else tc.get("arguments", {})
        if isinstance(raw_args, str):
            try:
                raw_args = json.loads(raw_args)
            except Exception:
                raw_args = {}
        if not isinstance(raw_args, dict):
            raw_args = {}

        steps.append(
            PlanStep(
                id=idx,
                description=f"Execute {tool_name}",
                tool=tool_name,
                parameters=raw_args,
            )
        )
    if not steps:
        return None
    return Plan(goal=goal, steps=steps)

