"""NOVA — Agent State Routes.

Exposes the agent's state machine and tool registry via REST so the
frontend can introspect the agent without tight coupling.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.agent.states import AgentState
from app.agent.tool_registry import list_tools, get_tools_schema

router = APIRouter(tags=["agent"])


@router.get("/api/agent/states")
async def get_agent_states():
    """Return all defined agent states with descriptions."""
    descriptions = {
        AgentState.IDLE: "Agent is ready and waiting for input.",
        AgentState.LISTENING: "STT is active; user audio is being captured.",
        AgentState.THINKING: "NLP analysis and intent routing in progress.",
        AgentState.UNDERSTANDING: "Understanding the user's larger goal.",
        AgentState.PLANNING: "Creating and validating a multi-step plan.",
        AgentState.EXECUTING: "A tool is being called.",
        AgentState.WAITING_FOR_USER: "Waiting for the user to clarify or confirm.",
        AgentState.REPLANNING: "Adapting the task plan to new observations.",
        AgentState.VERIFYING: "Checking whether the goal was completed.",
        AgentState.COMPLETED: "The planned task completed successfully.",
        AgentState.FAILED: "The planned task could not be completed.",
        AgentState.RESPONDING: "LLM is generating the final response.",
        AgentState.ERROR: "A recoverable error occurred.",
    }
    return {
        "states": [
            {"name": state.value, "description": descriptions[state]}
            for state in AgentState
        ]
    }


@router.get("/api/agent/tools")
async def get_tools():
    """Return all registered tools with their schemas."""
    tools = list_tools()
    return {
        "count": len(tools),
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required,
                        "default": p.default,
                    }
                    for p in t.parameters
                ],
            }
            for t in tools
        ],
        "schemas": get_tools_schema(),
    }
