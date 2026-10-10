"""Nova Pipeline — Speech-to-Text Transcriber.

Wraps ``faster-whisper`` (preferred) or ``openai-whisper`` (fallback)
for transcribing audio segments to text.  Model is lazy-loaded on first
call and cached as a singleton.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Optional

import numpy as np
import structlog

from nova.config import NovaConfig, get_config
from nova.interfaces import AudioSegment, Transcript

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Model singleton
# ---------------------------------------------------------------------------

_stt_model: dict | None = None


def _get_model(config: NovaConfig | None = None) -> dict | None:
    """Lazy-load the STT model. Returns a dict with 'engine' and 'model'."""
    global _stt_model
    if _stt_model is not None:
        return _stt_model

    cfg = config or get_config()

    # Try faster-whisper first (preferred)
    try:
        from faster_whisper import WhisperModel

        logger.info(
            "nova_loading_stt_model",
            engine="faster-whisper",
            model=cfg.stt_model,
            device=cfg.stt_device,
        )
        _stt_model = {
            "engine": "faster_whisper",
            "model": WhisperModel(
                cfg.stt_model,
                device=cfg.stt_device,
                compute_type=cfg.stt_compute_type,
            ),
        }
        logger.info("nova_stt_model_loaded", engine="faster-whisper")
        return _stt_model
    except ImportError:
        logger.info("nova_faster_whisper_not_available")

    # Fallback to openai-whisper
    try:
        import whisper

        logger.info("nova_loading_stt_model", engine="whisper", model=cfg.stt_model)
        _stt_model = {
            "engine": "whisper",
            "model": whisper.load_model(cfg.stt_model),
        }
        logger.info("nova_stt_model_loaded", engine="whisper")
        return _stt_model
    except ImportError:
        logger.warning("nova_no_stt_engine_available")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def transcribe(
    segment: AudioSegment,
    *,
    language: str | None = None,
    config: NovaConfig | None = None,
) -> Transcript:
    """Transcribe an audio segment to text.

    Args:
        segment: The audio segment to transcribe.
        language: Override language code (default from config).
        config: Optional config override.

    Returns:
        A ``Transcript`` with the recognised text, confidence, and timing.

    Raises:
        RuntimeError: If no STT engine is available.
    """
    cfg = config or get_config()
    lang = language or cfg.stt_language

    model_info = _get_model(cfg)
    if model_info is None:
        raise RuntimeError(
            "No speech recognition engine available.  "
            "Install faster-whisper or openai-whisper."
        )

    # Write segment audio to a temp file (whisper APIs expect a file path)
    tmp_dir = str(cfg.audio_temp_dir)
    tmp_file = tempfile.NamedTemporaryFile(
        suffix=".wav", dir=tmp_dir, delete=False,
    )
    try:
        _write_wav(tmp_file.name, segment.audio_bytes, segment.sample_rate)
        start = time.perf_counter()

        if model_info["engine"] == "faster_whisper":
            text, confidence = _transcribe_faster_whisper(
                model_info["model"], tmp_file.name, lang,
            )
        elif model_info["engine"] == "whisper":
            text, confidence = _transcribe_whisper(
                model_info["model"], tmp_file.name, lang,
            )
        else:
            raise RuntimeError(f"Unknown STT engine: {model_info['engine']}")

        duration_ms = int((time.perf_counter() - start) * 1000)

        logger.debug(
            "nova_transcription_complete",
            text_len=len(text),
            confidence=confidence,
            duration_ms=duration_ms,
            language=lang,
        )

        return Transcript(
            text=text,
            language=lang,
            confidence=confidence,
            duration_ms=duration_ms,
        )
    finally:
        # Clean up temp file
        Path(tmp_file.name).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Engine-specific transcription
# ---------------------------------------------------------------------------

def _transcribe_faster_whisper(
    model, audio_path: str, language: str,
) -> tuple[str, float | None]:
    """Transcribe using faster-whisper and extract confidence."""
    segments, info = model.transcribe(audio_path, language=language, beam_size=5)

    text_parts: list[str] = []
    log_probs: list[float] = []

    for seg in segments:
        text_parts.append(seg.text)
        if hasattr(seg, "avg_logprob"):
            log_probs.append(seg.avg_logprob)

    text = " ".join(text_parts).strip()

    # Convert average log-probability to a 0–1 confidence score
    confidence: float | None = None
    if log_probs:
        avg_log_prob = sum(log_probs) / len(log_probs)
        # log-prob is typically between -1.0 (good) and -3.0 (poor)
        # Map to 0–1 range: -1.0 → 1.0, -3.0 → 0.0
        confidence = max(0.0, min(1.0, (avg_log_prob + 3.0) / 2.0))

    return text, confidence


def _transcribe_whisper(
    model, audio_path: str, language: str,
) -> tuple[str, float | None]:
    """Transcribe using openai-whisper."""
    result = model.transcribe(audio_path, language=language)
    text = result.get("text", "").strip()
    return text, None  # openai-whisper doesn't expose per-segment confidence


# ---------------------------------------------------------------------------
# WAV writer (minimal, no pydub dependency)
# ---------------------------------------------------------------------------

def _write_wav(path: str, pcm_bytes: bytes, sample_rate: int) -> None:
    """Write raw 16-bit PCM bytes to a WAV file."""
    import struct

    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = len(pcm_bytes)
    file_size = 36 + data_size

    with open(path, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", file_size))
        f.write(b"WAVE")
        # fmt sub-chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # sub-chunk size
        f.write(struct.pack("<H", 1))   # PCM format
        f.write(struct.pack("<H", num_channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", bits_per_sample))
        # data sub-chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(pcm_bytes)


def is_available(config: NovaConfig | None = None) -> bool:
    """Check if an STT engine is available."""
    try:
        return _get_model(config) is not None
    except Exception:
        return False
