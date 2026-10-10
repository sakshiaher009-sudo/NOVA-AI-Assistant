"""NOVA — FastAPI Application Entry Point."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database.database import init_db, close_db
from app.api.routes_health import router as health_router
from app.api.routes_chat import router as chat_router
from app.api.routes_voice import router as voice_router
from app.api.routes_conversations import router as conversations_router
from app.api.routes_documents import router as documents_router
from app.api.routes_settings import router as settings_router
from app.api.routes_analytics import router as analytics_router
from app.api.routes_agent import router as agent_router
from app.api.routes_auth import router as auth_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()
    logger.info("nova_starting", app_name=settings.app_name, env=settings.environment)

    # Initialize database
    await init_db()
    logger.info("database_initialized")

    # Initialize wake word detector
    try:
        from app.speech.wake_word import get_wake_word_detector
        detector = get_wake_word_detector()
        logger.info("wake_word_initialized", available=detector.is_available)
    except Exception as e:
        logger.warning("wake_word_init_error", error=str(e))

    # Start background reminder scheduler
    try:
        from app.services.reminder_scheduler import get_reminder_scheduler
        scheduler = get_reminder_scheduler()
        scheduler.start()
    except Exception as e:
        logger.warning("reminder_scheduler_init_error", error=str(e))

    yield

    # Shutdown
    try:
        from app.services.reminder_scheduler import get_reminder_scheduler
        get_reminder_scheduler().stop()
    except Exception:
        pass

    await close_db()
    from app.llm.ollama_client import close_client
    await close_client()
    logger.info("nova_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="NOVA — Local AI Voice Agent",
        description="A full-stack conversational AI voice agent running entirely on your machine.",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(voice_router)
    app.include_router(conversations_router)
    app.include_router(documents_router)
    app.include_router(settings_router)
    app.include_router(analytics_router)
    app.include_router(agent_router)
    app.include_router(auth_router)

    return app


app = create_app()
