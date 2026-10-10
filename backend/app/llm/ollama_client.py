"""NOVA — Ollama LLM Client (async HTTP)."""

from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncGenerator, Optional

import httpx
import structlog

from app.config import get_settings
from app.llm.schemas import LLMMessage, LLMResponse, ModelInfo

logger = structlog.get_logger(__name__)

# Module-level client singleton (lazy)
_client: Optional[httpx.AsyncClient] = None
_client_loop: Optional[asyncio.AbstractEventLoop] = None


async def _get_client() -> httpx.AsyncClient:
    global _client, _client_loop
    current_loop = asyncio.get_running_loop()
    if _client is None or _client.is_closed or _client_loop is not current_loop:
        settings = get_settings()
        _client = httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=httpx.Timeout(settings.ollama_timeout, connect=10.0),
        )
        _client_loop = current_loop
    return _client


async def close_client() -> None:
    global _client, _client_loop
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
        _client_loop = None


async def health_check() -> bool:
    """Check if Ollama is reachable."""
    try:
        client = await _get_client()
        resp = await client.get("/")
        return resp.status_code == 200
    except Exception as e:
        logger.warning("ollama_health_check_failed", error=str(e))
        return False


async def list_models() -> list[ModelInfo]:
    """List locally available Ollama models."""
    try:
        client = await _get_client()
        resp = await client.get("/api/tags")
        resp.raise_for_status()
        data = resp.json()
        return [
            ModelInfo(
                name=m.get("name", ""),
                size=m.get("size"),
                modified_at=m.get("modified_at"),
                digest=m.get("digest"),
            )
            for m in data.get("models", [])
        ]
    except Exception as e:
        logger.error("ollama_list_models_failed", error=str(e))
        return []


async def model_available(model_name: Optional[str] = None) -> bool:
    """Check if a specific model is available locally."""
    settings = get_settings()
    target = model_name or settings.ollama_model
    models = await list_models()
    return any(m.name == target or m.name.startswith(target.split(":")[0]) for m in models)


async def chat(
    messages: list[LLMMessage],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    tools: Optional[list[dict]] = None,
) -> LLMResponse:
    """Send a chat completion request to Ollama (non-streaming)."""
    settings = get_settings()
    model_name = model or settings.ollama_model
    client = await _get_client()

    payload = {
        "model": model_name,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": False,
        "options": {"temperature": temperature},
    }
    if max_tokens:
        payload["options"]["num_predict"] = max_tokens
    if tools:
        payload["tools"] = tools

    start = time.perf_counter_ns()
    retries = settings.ollama_max_retries
    last_error: Optional[Exception] = None

    for attempt in range(retries):
        try:
            resp = await client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            elapsed_ns = time.perf_counter_ns() - start

            message_data = data.get("message", {})
            return LLMResponse(
                content=message_data.get("content", ""),
                model=data.get("model", model_name),
                total_duration_ns=data.get("total_duration", elapsed_ns),
                prompt_eval_count=data.get("prompt_eval_count"),
                eval_count=data.get("eval_count"),
                tool_calls=message_data.get("tool_calls", []),
            )
        except Exception as e:
            last_error = e
            logger.warning("ollama_chat_retry", attempt=attempt + 1, error=str(e))
            if attempt < retries - 1:
                import asyncio
                await asyncio.sleep(1 * (attempt + 1))

    raise ConnectionError(f"Ollama chat failed after {retries} retries: {last_error}")


async def chat_stream(
    messages: list[LLMMessage],
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Stream a chat completion from Ollama, yielding text chunks."""
    settings = get_settings()
    model_name = model or settings.ollama_model
    client = await _get_client()

    payload = {
        "model": model_name,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": True,
        "options": {"temperature": temperature},
    }

    async with client.stream("POST", "/api/chat", json=payload) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    yield chunk
                if data.get("done"):
                    break
            except json.JSONDecodeError:
                continue


async def generate(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.3,
    format: Optional[str] = None,
) -> str:
    """Simple one-shot text generation (for NLP tasks like intent classification and verification)."""
    settings = get_settings()
    model_name = model or settings.ollama_model
    client = await _get_client()

    payload = {
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

