"""NOVA — Health & Status Routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.analytics import HealthResponse, StatusResponse
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(status="ok", app_name=get_settings().app_name)


@router.get("/api/status", response_model=StatusResponse)
async def status():
    """Detailed system status."""
    from app.llm.model_manager import get_status
    from app.speech import stt, tts
    from app.rag import vector_store
    from app.database.database import get_db_session

    settings = get_settings()
    llm_status = await get_status()

    db_ok = False
    try:
        async with get_db_session() as session:
            db_ok = True
    except Exception:
        pass

    return StatusResponse(
        status="ok",
        ollama_available=llm_status["ollama_running"],
        ollama_model=settings.ollama_model,
        stt_available=stt.is_available(),
        tts_available=tts.is_available(),
        database_ok=db_ok,
        vector_db_ok=vector_store.is_available(),
    )
