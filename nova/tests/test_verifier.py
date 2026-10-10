"""Tests for nova.verifier — post-execution result verification."""

from nova.interfaces import PlanStep, ToolResult, VerificationResult
from nova.verifier import verify, verify_all


class TestVerify:
    """Test individual step verification."""

    def test_success_with_result(self):
        step = PlanStep(tool_name="calc")
        result = ToolResult(success=True, result="42")
        v = verify(step, result)
        assert v.passed is True

    def test_failure_flag(self):
        step = PlanStep(tool_name="calc")
        result = ToolResult(success=False, error="boom")
        v = verify(step, result)
        assert v.passed is False
        assert "failure" in v.details.lower()

    def test_none_result(self):
        step = PlanStep(tool_name="calc")
        result = ToolResult(success=True, result=None)
        v = verify(step, result)
        assert v.passed is False
        assert "None" in v.details

    def test_empty_string_result(self):
        step = PlanStep(tool_name="calc")
        result = ToolResult(success=True, result="")
        v = verify(step, result)
        assert v.passed is False
        assert "empty" in v.details.lower()

    def test_empty_list_result(self):
        step = PlanStep(tool_name="calc")
        result = ToolResult(success=True, result=[])
        v = verify(step, result)
        assert v.passed is False

    def test_empty_dict_result(self):
        step = PlanStep(tool_name="calc")
        result = ToolResult(success=True, result={})
        v = verify(step, result)
        assert v.passed is False

    def test_expected_type_match(self):
        step = PlanStep(tool_name="calc", expected_type="string")
        result = ToolResult(success=True, result="hello")
        v = verify(step, result)
        assert v.passed is True

    def test_expected_type_mismatch(self):
        step = PlanStep(tool_name="calc", expected_type="list")
        result = ToolResult(success=True, result="not a list")
        v = verify(step, result)
        assert v.passed is False
        assert "expected" in v.details.lower()

    def test_expected_type_number(self):
        step = PlanStep(tool_name="calc", expected_type="number")
        result = ToolResult(success=True, result=42)
        v = verify(step, result)
        assert v.passed is True

    def test_expected_type_number_float(self):
        step = PlanStep(tool_name="calc", expected_type="number")
        result = ToolResult(success=True, result=3.14)
        v = verify(step, result)
        assert v.passed is True

    def test_unknown_expected_type_passes(self):
        step = PlanStep(tool_name="calc", expected_type="custom_type")
        result = ToolResult(success=True, result="anything")
        v = verify(step, result)
        assert v.passed is True  # Unknown types are skipped


class TestVerifyAll:
    """Test batch verification."""

    def test_all_pass(self):
        steps = [PlanStep(tool_name="a"), PlanStep(tool_name="b")]
        results = [
            ToolResult(success=True, result="x"),
            ToolResult(success=True, result="y"),
        ]
        vs = verify_all(steps, results)
        assert len(vs) == 2
        assert all(v.passed for v in vs)

    def test_partial_failure(self):
        steps = [PlanStep(tool_name="a"), PlanStep(tool_name="b")]
        results = [
            ToolResult(success=True, result="x"),
            ToolResult(success=False, error="fail"),
        ]
        vs = verify_all(steps, results)
        assert vs[0].passed is True
        assert vs[1].passed is False

    def test_fewer_results_than_steps(self):
        """When fail-fast stops early, we have fewer results than steps."""
        steps = [PlanStep(tool_name="a"), PlanStep(tool_name="b")]
        results = [ToolResult(success=False, error="stopped")]
        vs = verify_all(steps, results)
        assert len(vs) == 1
