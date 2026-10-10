"""NOVA — Calculator Tool (safe math evaluation)."""

from __future__ import annotations

import ast
import math
import operator
from typing import Any

from app.tools.base import BaseTool, ToolParameter, ToolResult


# Safe operators for math evaluation
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Safe math functions
_SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "pi": math.pi,
    "e": math.e,
}


def _safe_eval(node: ast.AST) -> float:
    """Recursively evaluate an AST node using only safe operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant: {node.value}")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if op_type == ast.Div and right == 0:
            raise ValueError("Division by zero")
        if op_type == ast.Pow and (right > 1000 or left > 1e10):
            raise ValueError("Exponent too large")
        return _SAFE_OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return _SAFE_OPERATORS[op_type](_safe_eval(node.operand))
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCTIONS:
            func = _SAFE_FUNCTIONS[node.func.id]
            if callable(func):
                args = [_safe_eval(a) for a in node.args]
                return float(func(*args))
        raise ValueError(f"Unsupported function call")
    elif isinstance(node, ast.Name):
        if node.id in _SAFE_FUNCTIONS:
            val = _SAFE_FUNCTIONS[node.id]
            if isinstance(val, (int, float)):
                return float(val)
        raise ValueError(f"Unsupported variable: {node.id}")
    else:
        raise ValueError(f"Unsupported expression: {type(node).__name__}")


def safe_calculate(expression: str) -> float:
    """Safely evaluate a math expression without using eval()."""
    # Clean up common patterns
    expr = expression.replace("^", "**").replace("×", "*").replace("÷", "/")
    expr = expr.strip().rstrip("=").rstrip("?").strip()

    tree = ast.parse(expr, mode="eval")
    return _safe_eval(tree)


class CalculatorTool(BaseTool):
    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Evaluate mathematical expressions safely. Supports +, -, *, /, **, sqrt, abs, sin, cos, tan, log."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="expression",
                type="string",
                description="The math expression to evaluate, e.g. '987 * 43'",
            )
        ]

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        expression = str(params.get("expression", ""))
        if not expression:
            return ToolResult(success=False, error="No expression provided")

        try:
            result = safe_calculate(expression)
            # Format nicely
            if result == int(result):
                formatted = str(int(result))
            else:
                formatted = f"{result:.6g}"

            return ToolResult(
                success=True,
                result=result,
                display_text=f"{expression} = {formatted}",
            )
        except (ValueError, SyntaxError, TypeError) as e:
            return ToolResult(success=False, error=f"Cannot calculate: {str(e)}")
