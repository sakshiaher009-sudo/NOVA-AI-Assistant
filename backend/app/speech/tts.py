"""NOVA — Text-to-Speech Engine."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


async def synthesize(text: str, output_path: Optional[str] = None, voice: Optional[str] = None, speed: Optional[float] = None) -> str:
    """
    Synthesize speech from text.

    Returns path to generated WAV file.
    """
    settings = get_settings()
    engine = settings.tts_engine
    voice = voice or settings.tts_piper_voice
    speed = speed or settings.tts_speed

    if engine == "piper":
        return await _synthesize_piper(text, output_path, voice, speed)
    elif engine == "macos":
        return await _synthesize_macos(text, output_path, speed)
    else:
        raise RuntimeError(f"Unknown TTS engine: {engine}")


async def _synthesize_macos(text: str, output_path: Optional[str] = None, speed: float = 1.0) -> str:
    """Use macOS built-in 'say' command for TTS."""
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".aiff", dir=_get_audio_dir())

    start = time.perf_counter()

    # Calculate rate (default ~200 wpm, adjust by speed)
    rate = int(200 * speed)

    # macOS say command outputs AIFF
    aiff_path = output_path.replace(".wav", ".aiff") if output_path.endswith(".wav") else output_path

    try:
        result = subprocess.run(
            ["say", "-r", str(rate), "-o", aiff_path, "--", text],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"macOS say failed: {result.stderr}")

        # Convert AIFF to WAV using afconvert (built into macOS)
        wav_path = aiff_path.replace(".aiff", ".wav")
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@22050", aiff_path, wav_path],
            capture_output=True, text=True, timeout=15,
        )
        # Clean up AIFF
        if os.path.exists(aiff_path) and aiff_path != wav_path:
            os.unlink(aiff_path)

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info("tts_complete", engine="macos", duration_ms=duration_ms)
        return wav_path

    except subprocess.TimeoutExpired:
        raise RuntimeError("TTS timed out")
    except FileNotFoundError:
        raise RuntimeError("macOS 'say' command not found")


async def _synthesize_piper(
    text: str, output_path: Optional[str] = None, voice: str = "en_US-lessac-medium", speed: float = 1.0
) -> str:
    """Use Piper TTS for synthesis."""
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".wav", dir=_get_audio_dir())

    try:
        result = subprocess.run(
            ["piper", "--model", voice, "--output_file", output_path],
            input=text,
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Piper TTS failed: {result.stderr}")

        logger.info("tts_complete", engine="piper", voice=voice)
        return output_path

    except FileNotFoundError:
        logger.warning("piper_not_found, falling back to macOS say")
        return await _synthesize_macos(text, output_path, speed)


def _get_audio_dir() -> str:
    """Get the audio temp directory."""
    settings = get_settings()
    audio_dir = settings.data_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    return str(audio_dir)


def is_available() -> bool:
    """Check if TTS is available."""
    settings = get_settings()
    if settings.tts_engine == "macos":
        try:
            result = subprocess.run(["which", "say"], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False
    elif settings.tts_engine == "piper":
        try:
            result = subprocess.run(["which", "piper"], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False
    return False
