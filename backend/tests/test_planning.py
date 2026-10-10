"""Focused tests for NOVA Phase 4 planning and task context."""

import pytest
from app.agent.planner import create_plan
from app.agent.task_context import TaskContext


def test_create_plan_for_multi_step_project_request():
    plan = create_plan("Find my React project and check why it is not running")
    assert plan is not None
    assert [step.tool for step in plan.steps] == ["file_search", "read_file", "execute_terminal"]
    assert plan.validate_plan() is None


def test_task_context_resolves_previous_observation():
    plan = create_plan("Find my React project and inspect it")
    assert plan is not None
    context = TaskContext(original_goal=plan.goal, plan=plan)
    context.observations[1] = {"files": [{"path": "/Users/test/package.json"}]}
    assert context.resolve_parameters(plan.steps[1].parameters) == {
        "file_path": "/Users/test/package.json"
    }


def test_plan_from_tool_calls_parsing():
    from app.agent.planner import plan_from_tool_calls

    tool_calls = [
        {
            "function": {
                "name": "file_search",
                "arguments": {"query": "main.py"},
            }
        },
        {
            "function": {
                "name": "read_file",
                "arguments": {"file_path": "$step.1.files[0].path"},
            }
        },
    ]
    plan = plan_from_tool_calls("Find and inspect main.py", tool_calls)
    assert plan is not None
    assert len(plan.steps) == 2
    assert plan.steps[0].tool == "file_search"
    assert plan.steps[0].parameters == {"query": "main.py"}
    assert plan.steps[1].tool == "read_file"
    assert plan.steps[1].parameters == {"file_path": "$step.1.files[0].path"}


def test_fast_path_detection():
    from app.agent.orchestrator import _is_fast_path
    from app.schemas.chat import NLPResult

    # Fast path should fire for high-confidence time and calculate
    assert _is_fast_path(NLPResult(intent="GET_TIME", confidence=0.96)) is True
    assert _is_fast_path(NLPResult(intent="CALCULATE", confidence=0.95)) is True

    # Fast path should NOT fire for low confidence, or multi-step/ambiguous intents
    assert _is_fast_path(NLPResult(intent="GET_TIME", confidence=0.85)) is False
    assert _is_fast_path(NLPResult(intent="FILE_SEARCH", confidence=0.95)) is False
    assert _is_fast_path(NLPResult(intent="EXECUTE_TERMINAL", confidence=0.95)) is False
    assert _is_fast_path(NLPResult(intent="GENERAL_CONVERSATION", confidence=0.80)) is False


@pytest.mark.asyncio
async def test_verification_failure_triggers_honest_response(monkeypatch):
    from app.agent.orchestrator import _verify_tool_result, _handle_verification_failure

    # Empty file search result should fail verification
    empty_result = {"files": [], "total_matches": 0}
    is_valid, reason = await _verify_tool_result("Find my config", "file_search", empty_result)
    assert is_valid is False
    assert "files" in reason.lower()

    # Non-zero exit code in terminal execution should fail verification
    failed_cmd = {"exit_code": 127, "stderr": "command not found"}
    is_valid_cmd, reason_cmd = await _verify_tool_result("Check my tool", "execute_terminal", failed_cmd)
    assert is_valid_cmd is False

    # Honest failure response generator
    failure_reply = await _handle_verification_failure(
        "Find my config", "file_search", empty_result, reason, []
    )
    assert any(
        w in failure_reply.lower()
        for w in ["sorry", "don't know", "context", "clarify", "couldn't", "file_search", "more information"]
    )


@pytest.mark.asyncio
async def test_verification_catches_wrong_data_via_llm():
    from app.agent.orchestrator import _verify_tool_result

    # Tool "succeeds" with technically-present-but-wrong data (wrong expression evaluated)
    wrong_calc_result = {
        "expression": "2 + 2",
        "result": 4,
        "display_text": "2 + 2 = 4",
    }
    is_valid, reason = await _verify_tool_result(
        "What is 100 * 5?", "calculator", wrong_calc_result
    )
    assert is_valid is False
    assert len(reason) > 0


@pytest.mark.asyncio
async def test_verification_fail_open_on_exception(monkeypatch):
    from app.agent.orchestrator import _verify_tool_result
    from app.llm import ollama_client

    async def fail_generate(*args, **kwargs):
        raise TimeoutError("Ollama connection timed out")

    monkeypatch.setattr(ollama_client, "generate", fail_generate)

    is_valid, reason = await _verify_tool_result(
        "What is 100 * 5?", "calculator", {"result": 4}
    )
    assert is_valid is True
    assert "fail open" in reason.lower() or "skipped" in reason.lower()