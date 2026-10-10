"""Nova Pipeline — Self-contained Configuration.

Reads ONLY from environment variables prefixed with NOVA_ or from a .env file.
Never imports from the main project's config.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class NovaConfig(BaseSettings):
    """Configuration for the Nova voice assistant pipeline.

    All settings are read from environment variables with the NOVA_ prefix,
    or from a .env file. Sensible defaults are provided for local operation.
    """

    # --- LLM (Ollama) ---
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        description="Base URL for the Ollama API server.",
    )
    ollama_model: str = Field(
        default="llama3.2:1b",
        description="Ollama model name for inference.",
    )
    ollama_timeout: int = Field(
        default=120,
        description="HTTP timeout in seconds for Ollama requests.",
    )
    ollama_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for failed Ollama calls.",
    )

    # --- Speech-to-Text (faster-whisper) ---
    stt_model: str = Field(
        default="base",
        description="Whisper model size: tiny, base, small, medium, large.",
    )
    stt_language: str = Field(
        default="en",
        description="Language code for transcription.",
    )
    stt_device: str = Field(
        default="cpu",
        description="Device for STT inference: cpu or cuda.",
    )
    stt_compute_type: str = Field(
        default="int8",
        description="Compute type for faster-whisper: int8, float16, float32.",
    )

    # --- Text-to-Speech ---
    tts_engine: str = Field(
        default="macos",
        description="TTS engine: 'macos' (say command) or 'piper'.",
    )
    tts_piper_voice: str = Field(
        default="en_US-lessac-medium",
        description="Piper TTS voice model name.",
    )
    tts_speed: float = Field(
        default=1.0,
        description="Speech rate multiplier for TTS output.",
    )

    # --- VAD ---
    vad_threshold: float = Field(
        default=0.5,
        description="Speech probability threshold for VAD (0.0–1.0).",
    )
    vad_min_speech_duration_ms: int = Field(
        default=250,
        description="Minimum duration (ms) to consider as speech.",
    )
    vad_min_silence_duration_ms: int = Field(
        default=300,
        description="Minimum silence (ms) to mark end of speech.",
    )

    # --- Validator ---
    validator_min_confidence: float = Field(
        default=0.4,
        description="Minimum transcription confidence to treat as CLEAR.",
    )
    validator_min_length: int = Field(
        default=2,
        description="Minimum character count to treat as CLEAR.",
    )

    # --- Logging ---
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR.",
    )

    model_config = {
        "env_prefix": "NOVA_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @property
    def nova_root(self) -> Path:
        """Return the nova package directory."""
        return Path(__file__).resolve().parent

    @property
    def audio_temp_dir(self) -> Path:
        """Return a temp directory for audio files."""
        d = self.nova_root.parent / "data" / "nova_audio"
        d.mkdir(parents=True, exist_ok=True)
        return d


@lru_cache
def get_config() -> NovaConfig:
    """Return the cached Nova configuration singleton."""
    return NovaConfig()
