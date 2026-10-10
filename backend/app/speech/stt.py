"""NOVA — Speech-to-Text Engine."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Optional

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

_stt_model = None


def _get_model():
    """Lazy-load the STT model."""
    global _stt_model
    if _stt_model is not None:
        return _stt_model

    settings = get_settings()

    # Try faster-whisper first
    try:
        from faster_whisper import WhisperModel

        logger.info("loading_stt_model", engine="faster-whisper", model=settings.stt_model)
        _stt_model = {
            "engine": "faster_whisper",
            "model": WhisperModel(
                settings.stt_model,
                device=settings.stt_device,
                compute_type=settings.stt_compute_type,
            ),
        }
        logger.info("stt_model_loaded", engine="faster-whisper")
        return _stt_model
    except ImportError:
        logger.info("faster_whisper_not_available, trying whisper")
    except Exception as e:
        logger.warning("faster_whisper_init_failed_trying_default_cpu", error=str(e))
        try:
            from faster_whisper import WhisperModel
            _stt_model = {
                "engine": "faster_whisper",
                "model": WhisperModel(
                    settings.stt_model,
                    device="cpu",
                    compute_type="default",
                ),
            }
            logger.info("stt_model_loaded_default", engine="faster-whisper")
            return _stt_model
        except Exception as err2:
            logger.warning("faster_whisper_load_failed", error=str(err2))

    # Fallback to openai-whisper
    try:
        import whisper

        logger.info("loading_stt_model", engine="whisper", model=settings.stt_model)
        _stt_model = {
            "engine": "whisper",
            "model": whisper.load_model(settings.stt_model),
        }
        logger.info("stt_model_loaded", engine="whisper")
        return _stt_model
    except ImportError:
        logger.warning("no_stt_engine_available")
        return None


async def transcribe(audio_path: str, language: str = "en") -> dict:
    """
    Transcribe audio file to text.

    Returns dict with: text, language, confidence, duration_ms
    """
    model_info = _get_model()
    if model_info is None:
        raise RuntimeError(
            "No speech recognition engine available. "
            "Install faster-whisper or openai-whisper."
        )

    start = time.perf_counter()

    if model_info["engine"] == "faster_whisper":
        segments, info = model_info["model"].transcribe(
            audio_path, language=language, beam_size=5
        )
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text)
        text = " ".join(text_parts).strip()
        detected_lang = info.language if info else language

    elif model_info["engine"] == "whisper":
        result = model_info["model"].transcribe(audio_path, language=language)
        text = result.get("text", "").strip()
        detected_lang = result.get("language", language)

    else:
        raise RuntimeError("Unknown STT engine")

    duration_ms = int((time.perf_counter() - start) * 1000)

    logger.info("stt_complete", text_len=len(text), duration_ms=duration_ms, language=detected_lang)

    return {
        "text": text,
        "language": detected_lang,
        "confidence": None,  # Whisper doesn't provide overall confidence
        "duration_ms": duration_ms,
    }


def is_available() -> bool:
    """Check if STT engine is available."""
    try:
        return _get_model() is not None
    except Exception:
        return False
