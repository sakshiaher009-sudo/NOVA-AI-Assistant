"""NOVA Backend — Application Configuration."""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration loaded from environment / .env file."""

    # --- Application ---
    app_name: str = "NOVA"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    verbose_logging: bool = False

    # --- Backend ---
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000

    # --- Frontend ---
    frontend_port: int = 3000

    # --- Ollama LLM ---
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:1b"
    ollama_timeout: int = 120
    ollama_max_retries: int = 3

    # --- Speech-to-Text ---
    stt_model: str = "base"
    stt_language: str = "en"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"

    # --- Text-to-Speech ---
    tts_engine: str = "macos"
    tts_piper_voice: str = "en_US-lessac-medium"
    tts_speed: float = 1.0

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # --- Vector Database ---
    vector_db_path: str = "./data/chroma"
    embedding_model: str = "all-MiniLM-L6-v2"

    # --- Document Upload ---
    max_upload_mb: int = 25
    allowed_extensions: str = "pdf,txt,md,docx"

    # --- Security ---
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    jwt_secret: str = "nova-dev-secret-change-in-production-6f8a9b2c"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 72

    # --- Performance ---
    max_conversation_context: int = 20
    max_rag_results: int = 5
    chunk_size: int = 512
    chunk_overlap: int = 50

    # --- Reminders & Notifications ---
    reminder_poll_interval_seconds: int = 30

    # --- Wake Word Detection ---
    wake_word_model: str = "hey_jarvis"
    wake_word_model_path: Optional[str] = None
    wake_word_threshold: float = 0.5

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @property
    def project_root(self) -> Path:
        """Return the project root directory (nova/)."""
        return Path(__file__).resolve().parent.parent.parent

    @property
    def data_dir(self) -> Path:
        """Return the data directory."""
        return self.project_root / "data"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_extension_list(self) -> list[str]:
        """Parse allowed file extensions."""
        return [e.strip().lower() for e in self.allowed_extensions.split(",") if e.strip()]

    @property
    def max_upload_bytes(self) -> int:
        """Return max upload size in bytes."""
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
