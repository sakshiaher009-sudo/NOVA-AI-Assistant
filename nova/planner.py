"""Nova Pipeline — Command Planner.

Converts a COMMAND-classified transcript into an ordered ``ExecutionPlan``
of tool calls.  Uses the LLM to reason about which tools to invoke and
with what arguments.
"""

from __future__ import annotations

import json
import re

import structlog

from nova.config import NovaConfig, get_config
from nova.interfaces import ExecutionPlan, PlanStep, ToolSchema
from nova import llm_client

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

PLANNER_PROMPT_TEMPLATE = """\
You are a task planner for a voice assistant called Nova.

The user gave a command. Your job is to break it down into an ordered list of
tool calls using ONLY the available tools listed below.

Available tools:
{tools_description}

User command: "{command}"

Respond with ONLY a JSON object in this exact format (no markdown, no extra text):
{{
  "reasoning": "Brief explanation of your plan",
  "steps": [
    {{
      "tool_name": "exact_tool_name",
      "arguments": {{"param1": "value1"}},
      "description": "What this step does"
    }}
  ]
}}

Rules:
- Use ONLY tool names from the available tools list above.
- If no tool matches the command, return an empty steps list.
- Order steps logically (dependencies first).
- Keep arguments minimal and derived from the user's command.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_plan(
    command_text: str,
    available_tools: list[ToolSchema],
    *,
    config: NovaConfig | None = None,
) -> ExecutionPlan:
    """Convert a command into an ordered execution plan.

    Args:
        command_text: The user's command transcript.
        available_tools: Schemas of all registered tools.
        config: Optional config override.

    Returns:
        An ``ExecutionPlan`` with ordered steps (may be empty if no tools
        match the command).
    """
    cfg = config or get_config()
    tools_desc = _format_tools_description(available_tools)
    tool_names = {t.name for t in available_tools}

    prompt = PLANNER_PROMPT_TEMPLATE.format(
        tools_description=tools_desc,
        command=command_text,
    )

    try:
        raw = await llm_client.generate(
            prompt,
            temperature=0.2,
            format="json",
            config=cfg,
        )

        plan = _parse_plan_response(raw, command_text, tool_names)
        logger.debug(
            "nova_plan_created",
            command=command_text[:80],
            steps=len(plan.steps),
            reasoning=plan.reasoning[:120] if plan.reasoning else "",
        )
        return plan

    except Exception as exc:
        logger.warning("nova_planning_failed", error=str(exc))
        return ExecutionPlan(
            steps=[],
            original_command=command_text,
            reasoning=f"Planning failed: {exc}",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_tools_description(tools: list[ToolSchema]) -> str:
    """Format tool schemas into a readable string for the LLM prompt."""
    lines: list[str] = []
    for tool in tools:
        params = ""
        if tool.parameters:
            param_parts = []
            for p in tool.parameters:
                req = " (required)" if p.required else " (optional)"
                param_parts.append(f"    - {p.name}: {p.type}{req} — {p.description}")
            params = "\n" + "\n".join(param_parts)
        lines.append(f"- {tool.name}: {tool.description}{params}")
    return "\n".join(lines) if lines else "(No tools available)"


def _parse_plan_response(
    raw: str,
    original_command: str,
    valid_tool_names: set[str],
) -> ExecutionPlan:
    """Parse the LLM's JSON response into an ExecutionPlan."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return ExecutionPlan(
                    steps=[],
                    original_command=original_command,
                    reasoning="Failed to parse planner response as JSON.",
                )
        else:
            return ExecutionPlan(
                steps=[],
                original_command=original_command,
                reasoning="No JSON found in planner response.",
            )

    reasoning = data.get("reasoning", "")
    raw_steps = data.get("steps", [])

    steps: list[PlanStep] = []
    for s in raw_steps:
        tool_name = s.get("tool_name", "")
        if tool_name not in valid_tool_names:
            logger.warning(
                "nova_planner_unknown_tool",
                tool_name=tool_name,
                available=list(valid_tool_names),
            )
            continue  # Skip steps with unknown tools

        steps.append(PlanStep(
            tool_name=tool_name,
            arguments=s.get("arguments", {}),
            expected_type=s.get("expected_type"),
            description=s.get("description", ""),
        ))

    return ExecutionPlan(
        steps=steps,
        original_command=original_command,
        reasoning=reasoning,
    )
