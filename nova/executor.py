"""Nova Pipeline — Plan Executor.

Dispatches each ``PlanStep`` in an ``ExecutionPlan`` to the matching tool
in the ``ToolRegistry``.  Supports fail-fast (stop on first failure) or
continue-on-error modes.
"""

from __future__ import annotations

import time

import structlog

from nova.interfaces import ExecutionPlan, PlanStep, ToolResult

# Avoid circular import — ToolRegistry is typed via TYPE_CHECKING
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from nova.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)


async def execute_plan(
    plan: ExecutionPlan,
    registry: "ToolRegistry",
    *,
    fail_fast: bool = True,
) -> list[ToolResult]:
    """Execute all steps in a plan sequentially.

    Args:
        plan: The execution plan with ordered steps.
        registry: Tool registry to look up tools.
        fail_fast: If True, stop on the first failed step.

    Returns:
        List of ``ToolResult`` objects, one per executed step.
    """
    if not plan.steps:
        logger.debug("nova_executor_empty_plan", command=plan.original_command[:80])
        return [ToolResult(
            success=False,
            error="No executable steps in the plan.",
            display_text="I couldn't determine which tools to use for that command.",
        )]

    results: list[ToolResult] = []

    for i, step in enumerate(plan.steps):
        logger.debug(
            "nova_executor_step_start",
            step=i + 1,
            total=len(plan.steps),
            tool=step.tool_name,
            description=step.description,
        )

        result = await _execute_step(step, registry)
        results.append(result)

        logger.debug(
            "nova_executor_step_done",
            step=i + 1,
            tool=step.tool_name,
            success=result.success,
        )

        if not result.success and fail_fast:
            logger.warning(
                "nova_executor_fail_fast",
                step=i + 1,
                tool=step.tool_name,
                error=result.error,
            )
            break

    return results


async def _execute_step(
    step: PlanStep,
    registry: "ToolRegistry",
) -> ToolResult:
    """Execute a single plan step against the tool registry.

    Args:
        step: The plan step to execute.
        registry: Tool registry to look up the tool.

    Returns:
        A ``ToolResult`` from the tool execution.
    """
    tool = registry.get(step.tool_name)
    if tool is None:
        return ToolResult(
            success=False,
            error=f"Tool not found: {step.tool_name}",
            display_text=f"The tool '{step.tool_name}' is not available.",
        )

    start = time.perf_counter()
    try:
        result = await tool.safe_execute(step.arguments)
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.debug(
            "nova_tool_executed",
            tool=step.tool_name,
            success=result.success,
            duration_ms=duration_ms,
        )
        return result
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(
            "nova_tool_execution_error",
            tool=step.tool_name,
            error=str(exc),
            duration_ms=duration_ms,
        )
        return ToolResult(
            success=False,
            error=f"Tool execution error: {exc}",
            display_text=f"An error occurred while running '{step.tool_name}'.",
        )
