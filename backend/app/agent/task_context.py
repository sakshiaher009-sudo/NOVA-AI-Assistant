"""Per-request context for a multi-step NOVA task."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.agent.planner import Plan


class TaskContext(BaseModel):
    original_goal: str
    plan: Plan
    completed_steps: list[int] = Field(default_factory=list)
    observations: dict[int, Any] = Field(default_factory=dict)
    state: str = "planning"

    def resolve_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("$step."):
                resolved[key] = self._resolve_reference(value)
            else:
                resolved[key] = value
        return resolved

    def _resolve_reference(self, reference: str) -> Any:
        # References are intentionally limited to prior step observations.
        try:
            _, step_id, *path = reference.split(".")
            value: Any = self.observations[int(step_id)]
            for part in path:
                if part.endswith("]"):
                    field, index = part[:-1].split("[")
                    value = value[field][int(index)]
                else:
                    value = value[part]
            return value
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    def next_step(self) -> Optional[Any]:
        for step in self.plan.steps:
            if step.status == "pending":
                return step
        return None
