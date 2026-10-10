"""Nova Pipeline — Text-to-Speech Synthesis.

Converts final response text into audio.  Supports macOS ``say`` command
(default) and Piper TTS.  Fully self-contained — reads config from
``nova.config`` only.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time

import structlog

from nova.config import NovaConfig, get_config
from nova.interfaces import AudioResponse, NovaResponse

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def synthesize(
    response: NovaResponse,
    *,
    config: NovaConfig | None = None,
) -> AudioResponse:
    """Synthesize speech from a NovaResponse.

    Args:
        response: The response whose ``text`` will be spoken.
        config: Optional config override.

    Returns:
        An ``AudioResponse`` with the path to the generated audio file.
    """
    cfg = config or get_config()
    text = response.text.strip()

    if not text:
        text = "I have nothing to say."

    if cfg.tts_engine == "piper":
        audio_path = await _synthesize_piper(text, cfg)
    elif cfg.tts_engine == "macos":
        audio_path = await _synthesize_macos(text, cfg)
    else:
        raise RuntimeError(f"Unknown TTS engine: {cfg.tts_engine}")

    return AudioResponse(
        audio_path=audio_path,
        audio_format="wav",
        sample_rate=22050,
        text=text,
        nova_response=response,
    )


# ---------------------------------------------------------------------------
# macOS say
# ---------------------------------------------------------------------------

async def _synthesize_macos(text: str, cfg: NovaConfig) -> str:
    """Use macOS built-in ``say`` command for TTS."""
    audio_dir = str(cfg.audio_temp_dir)
    fd, aiff_path = tempfile.mkstemp(suffix=".aiff", dir=audio_dir)
    os.close(fd)

    start = time.perf_counter()
    rate = int(200 * cfg.tts_speed)

    try:
        result = subprocess.run(
            ["say", "-r", str(rate), "-o", aiff_path, "--", text],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"macOS say failed: {result.stderr}")

        # Convert AIFF → WAV using afconvert (built into macOS)
        wav_path = aiff_path.replace(".aiff", ".wav")
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@22050", aiff_path, wav_path],
            capture_output=True,
            text=True,
            timeout=15,
        )

        # Clean up AIFF
        if os.path.exists(aiff_path) and aiff_path != wav_path:
            os.unlink(aiff_path)

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.debug("nova_tts_complete", engine="macos", duration_ms=duration_ms)
        return wav_path

    except subprocess.TimeoutExpired:
        raise RuntimeError("TTS timed out")
    except FileNotFoundError:
        raise RuntimeError("macOS 'say' command not found")


# ---------------------------------------------------------------------------
# Piper TTS
# ---------------------------------------------------------------------------

async def _synthesize_piper(text: str, cfg: NovaConfig) -> str:
    """Use Piper TTS for synthesis."""
    audio_dir = str(cfg.audio_temp_dir)
    fd, output_path = tempfile.mkstemp(suffix=".wav", dir=audio_dir)
    os.close(fd)

    try:
        result = subprocess.run(
            ["piper", "--model", cfg.tts_piper_voice, "--output_file", output_path],
            input=text,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Piper TTS failed: {result.stderr}")

        logger.debug("nova_tts_complete", engine="piper", voice=cfg.tts_piper_voice)
        return output_path

    except FileNotFoundError:
        logger.warning("nova_piper_not_found_falling_back_to_macos")
        return await _synthesize_macos(text, cfg)


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def is_available(config: NovaConfig | None = None) -> bool:
    """Check if a TTS engine is available."""
    cfg = config or get_config()

    if cfg.tts_engine == "macos":
        try:
            result = subprocess.run(["which", "say"], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False

    if cfg.tts_engine == "piper":
        try:
            result = subprocess.run(["which", "piper"], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False

    return False
