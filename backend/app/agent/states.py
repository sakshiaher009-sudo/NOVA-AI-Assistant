"""NOVA — Agent State Machine.

Defines the formal agent states that represent the internal lifecycle
of the agent during request processing. These states are intentionally
decoupled from the frontend's JarvisState so either side can evolve
independently, while remaining mappable via the API.

States:
  IDLE        — Agent is ready, no active request.
  LISTENING   — STT is active; user audio is being captured.
  THINKING    — NLP + intent routing is in progress.
  EXECUTING   — A tool is being called.
  RESPONDING  — LLM is generating the final response.
  ERROR       — A recoverable error occurred; agent will return to IDLE.
"""

from __future__ import annotations

from enum import Enum


class AgentState(str, Enum):
    """Lifecycle states of the NOVA agent."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING_FOR_USER = "waiting_for_user"
    REPLANNING = "replanning"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    RESPONDING = "responding"
    ERROR = "error"
