"""Nova Pipeline — Post-Execution Verifier.

After a tool executes, the verifier checks whether the result matches
the planned intent: success flag, non-empty data, and expected type.
"""

from __future__ import annotations

import structlog

from nova.interfaces import PlanStep, ToolResult, VerificationResult

logger = structlog.get_logger(__name__)


def verify(
    plan_step: PlanStep,
    result: ToolResult,
) -> VerificationResult:
    """Verify a tool result against the plan step's expectations.

    Checks:
      1. ``result.success`` is True.
      2. ``result.result`` is not None and not empty.
      3. If ``plan_step.expected_type`` is set, the result type matches.

    Args:
        plan_step: The plan step that was executed.
        result: The tool result to verify.

    Returns:
        A ``VerificationResult`` indicating pass/fail with details.
    """
    # 1. Check success flag
    if not result.success:
        details = (
            f"Tool '{plan_step.tool_name}' reported failure: "
            f"{result.error or 'unknown error'}"
        )
        logger.debug("nova_verification_failed", reason="tool_failure", details=details)
        return VerificationResult(passed=False, details=details)

    # 2. Check for empty result
    if result.result is None:
        details = f"Tool '{plan_step.tool_name}' returned None."
        logger.debug("nova_verification_failed", reason="null_result", details=details)
        return VerificationResult(passed=False, details=details)

    if isinstance(result.result, (str, list, dict)) and len(result.result) == 0:
        details = f"Tool '{plan_step.tool_name}' returned empty {type(result.result).__name__}."
        logger.debug("nova_verification_failed", reason="empty_result", details=details)
        return VerificationResult(passed=False, details=details)

    # 3. Check expected type (if specified)
    if plan_step.expected_type:
        type_ok = _check_type(result.result, plan_step.expected_type)
        if not type_ok:
            details = (
                f"Tool '{plan_step.tool_name}' returned "
                f"{type(result.result).__name__}, expected {plan_step.expected_type}."
            )
            logger.debug("nova_verification_failed", reason="type_mismatch", details=details)
            return VerificationResult(passed=False, details=details)

    # All checks passed
    details = f"Tool '{plan_step.tool_name}' completed successfully."
    logger.debug("nova_verification_passed", tool=plan_step.tool_name)
    return VerificationResult(passed=True, details=details)


def verify_all(
    steps: list[PlanStep],
    results: list[ToolResult],
) -> list[VerificationResult]:
    """Verify all tool results against their corresponding plan steps.

    Args:
        steps: The plan steps that were executed.
        results: The tool results (may be shorter than steps if fail-fast).

    Returns:
        List of ``VerificationResult`` objects, one per result.
    """
    verifications: list[VerificationResult] = []
    for i, result in enumerate(results):
        step = steps[i] if i < len(steps) else PlanStep(tool_name="unknown")
        verifications.append(verify(step, result))
    return verifications


# ---------------------------------------------------------------------------
# Type checking helpers
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "string": str,
    "str": str,
    "number": (int, float),
    "int": int,
    "float": float,
    "bool": bool,
    "boolean": bool,
    "list": list,
    "array": list,
    "dict": dict,
    "object": dict,
}


def _check_type(value, expected: str) -> bool:
    """Check if a value matches the expected type string."""
    expected_types = _TYPE_MAP.get(expected.lower())
    if expected_types is None:
        # Unknown type — skip the check
        return True
    return isinstance(value, expected_types)
