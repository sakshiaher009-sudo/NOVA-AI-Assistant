"""Nova Pipeline — Standalone Ollama LLM Client.

Async HTTP client for the Ollama API.  Fully self-contained — reads config
from ``nova.config`` only, never imports from the main project.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import AsyncGenerator, Optional

import httpx
import structlog

from nova.config import NovaConfig, get_config

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    """Wrapper around a non-streaming Ollama chat/generate response."""
    content: str
    model: str = ""
    total_duration_ns: int = 0
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None
    tool_calls: list[dict] | None = None


# ---------------------------------------------------------------------------
# Client singleton (lazy, per-event-loop)
# ---------------------------------------------------------------------------

_client: Optional[httpx.AsyncClient] = None
_client_loop: Optional[asyncio.AbstractEventLoop] = None


async def _get_client(config: NovaConfig | None = None) -> httpx.AsyncClient:
    """Return (or create) a module-level async HTTP client."""
    global _client, _client_loop
    cfg = config or get_config()
    current_loop = asyncio.get_running_loop()

    if _client is None or _client.is_closed or _client_loop is not current_loop:
        _client = httpx.AsyncClient(
            base_url=cfg.ollama_base_url,
            timeout=httpx.Timeout(cfg.ollama_timeout, connect=10.0),
        )
        _client_loop = current_loop
    return _client


async def close_client() -> None:
    """Shut down the HTTP client (call on application exit)."""
    global _client, _client_loop
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
        _client_loop = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    config: NovaConfig | None = None,
) -> LLMResponse:
    """Send a chat-completion request to Ollama (non-streaming).

    Args:
        messages: List of ``{"role": ..., "content": ...}`` dicts.
        model: Override the model from config.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens to generate.
        config: Optional config override.

    Returns:
        An ``LLMResponse`` with the assistant's reply.

    Raises:
        ConnectionError: After exhausting retries.
    """
    cfg = config or get_config()
    model_name = model or cfg.ollama_model
    client = await _get_client(cfg)

    payload: dict = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if max_tokens:
        payload["options"]["num_predict"] = max_tokens

    start = time.perf_counter_ns()
    last_error: Exception | None = None

    for attempt in range(cfg.ollama_max_retries):
        try:
            resp = await client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            elapsed_ns = time.perf_counter_ns() - start

            msg = data.get("message", {})
            return LLMResponse(
                content=msg.get("content", ""),
                model=data.get("model", model_name),
                total_duration_ns=data.get("total_duration", elapsed_ns),
                prompt_eval_count=data.get("prompt_eval_count"),
                eval_count=data.get("eval_count"),
                tool_calls=msg.get("tool_calls"),
            )
        except Exception as exc:
            last_error = exc
            logger.warning(
                "nova_llm_chat_retry",
                attempt=attempt + 1,
                error=str(exc),
            )
            if attempt < cfg.ollama_max_retries - 1:
                await asyncio.sleep(1 * (attempt + 1))

    raise ConnectionError(
        f"Nova LLM chat failed after {cfg.ollama_max_retries} retries: {last_error}"
    )


async def generate(
    prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.3,
    format: str | None = None,
    config: NovaConfig | None = None,
) -> str:
    """One-shot text generation via Ollama ``/api/generate``.

    Useful for structured outputs (intent classification, planning) where
    the chat API's role structure is unnecessary.

    Args:
        prompt: The full prompt string.
        model: Override the model from config.
        temperature: Sampling temperature (lower = more deterministic).
        format: Optional response format (e.g., ``"json"``).
        config: Optional config override.

    Returns:
        The generated text string (stripped).
    """
    cfg = config or get_config()
    model_name = model or cfg.ollama_model
    client = await _get_client(cfg)

    payload: dict = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if format:
        payload["format"] = format

    resp = await client.post("/api/generate", json=payload)
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


async def health_check(config: NovaConfig | None = None) -> bool:
    """Return True if Ollama is reachable."""
    try:
        client = await _get_client(config)
        resp = await client.get("/")
        return resp.status_code == 200
    except Exception as exc:
        logger.warning("nova_llm_health_check_failed", error=str(exc))
        return False
