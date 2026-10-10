"""NOVA — LLM Model Manager."""

from __future__ import annotations

import structlog

from app.config import get_settings
from app.llm import ollama_client
from app.llm.schemas import ModelInfo

logger = structlog.get_logger(__name__)


async def get_status() -> dict:
    """Return LLM system status."""
    settings = get_settings()
    healthy = await ollama_client.health_check()
    available = False
    models: list[ModelInfo] = []

    if healthy:
        models = await ollama_client.list_models()
        available = any(
            m.name == settings.ollama_model or m.name.startswith(settings.ollama_model.split(":")[0])
            for m in models
        )

    return {
        "ollama_running": healthy,
        "model_configured": settings.ollama_model,
        "model_available": available,
        "models_installed": [m.name for m in models],
    }


async def ensure_model_ready() -> bool:
    """Check that Ollama is running and the configured model is available."""
    status = await get_status()
    if not status["ollama_running"]:
        logger.error("ollama_not_running")
        return False
    if not status["model_available"]:
        logger.error(
            "ollama_model_not_available",
            model=status["model_configured"],
            available=status["models_installed"],
        )
        return False
    return True
