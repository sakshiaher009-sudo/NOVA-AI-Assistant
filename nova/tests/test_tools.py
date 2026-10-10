"""Tests for nova.tools — base class ABC and registry."""

from typing import Any

import pytest

from nova.interfaces import ToolParameter, ToolResult
from nova.tools.base_tool import NovaTool
from nova.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Concrete test tool
# ---------------------------------------------------------------------------

class DummyTool(NovaTool):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "A dummy tool for testing"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="input", type="string", description="Input text", required=True),
        ]

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        return ToolResult(
            success=True,
            result=params.get("input", ""),
            display_text=f"Got: {params.get('input', '')}",
        )


class AnotherTool(NovaTool):
    @property
    def name(self) -> str:
        return "another"

    @property
    def description(self) -> str:
        return "Another tool"

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, result="ok")


# ---------------------------------------------------------------------------
# Test NovaTool base class
# ---------------------------------------------------------------------------

class TestNovaTool:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            NovaTool()  # type: ignore

    def test_concrete_tool_properties(self):
        tool = DummyTool()
        assert tool.name == "dummy"
        assert tool.description == "A dummy tool for testing"
        assert len(tool.parameters) == 1

    def test_schema_generation(self):
        tool = DummyTool()
        schema = tool.schema
        assert schema.name == "dummy"
        assert len(schema.parameters) == 1
        assert schema.parameters[0].name == "input"

    def test_validate_input_ok(self):
        tool = DummyTool()
        error = tool.validate_input({"input": "hello"})
        assert error is None

    def test_validate_input_missing_required(self):
        tool = DummyTool()
        error = tool.validate_input({})
        assert error is not None
        assert "input" in error

    def test_default_parameters_empty(self):
        tool = AnotherTool()
        assert tool.parameters == []


@pytest.mark.asyncio
class TestNovaToolExecution:
    async def test_execute(self):
        tool = DummyTool()
        result = await tool.execute({"input": "test"})
        assert result.success is True
        assert result.result == "test"

    async def test_safe_execute_success(self):
        tool = DummyTool()
        result = await tool.safe_execute({"input": "test"})
        assert result.success is True

    async def test_safe_execute_validation_failure(self):
        tool = DummyTool()
        result = await tool.safe_execute({})  # Missing required 'input'
        assert result.success is False
        assert "Missing" in result.error


# ---------------------------------------------------------------------------
# Test ToolRegistry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_empty_registry(self):
        reg = ToolRegistry()
        assert len(reg) == 0
        assert reg.get("anything") is None

    def test_register_and_get(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        assert reg.get("dummy") is not None
        assert reg.get("dummy").name == "dummy"

    def test_register_duplicate_raises(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(DummyTool())

    def test_unregister(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        assert reg.unregister("dummy") is True
        assert reg.get("dummy") is None
        assert len(reg) == 0

    def test_unregister_missing(self):
        reg = ToolRegistry()
        assert reg.unregister("nonexistent") is False

    def test_list_all(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        reg.register(AnotherTool())
        tools = reg.list_all()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"dummy", "another"}

    def test_get_schemas(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        schemas = reg.get_schemas()
        assert len(schemas) == 1
        assert schemas[0].name == "dummy"

    def test_get_names(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        reg.register(AnotherTool())
        assert set(reg.get_names()) == {"dummy", "another"}

    def test_contains(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        assert "dummy" in reg
        assert "nope" not in reg

    def test_repr(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        assert "dummy" in repr(reg)
