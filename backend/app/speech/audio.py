"""NOVA — Audio Utilities."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


async def convert_to_wav(input_path: str, output_path: Optional[str] = None) -> str:
    """Convert audio file to WAV format suitable for STT."""
    settings = get_settings()
    audio_dir = settings.data_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".wav", dir=str(audio_dir))
        os.close(fd)

    try:
        import shutil
        from pydub import AudioSegment
        import pydub.utils

        ffmpeg_bin = pydub.utils.which("ffmpeg") or shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
        if ffmpeg_bin and os.path.exists(ffmpeg_bin):
            AudioSegment.converter = ffmpeg_bin

        ffprobe_bin = pydub.utils.which("ffprobe") or shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
        if ffprobe_bin and os.path.exists(ffprobe_bin):
            pydub.utils.get_prober_name = lambda: ffprobe_bin

        audio = AudioSegment.from_file(input_path)
        # Convert to mono 16kHz 16-bit WAV (optimal for Whisper)
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
        audio.export(output_path, format="wav")
        logger.debug("audio_converted", input=input_path, output=output_path)
        return output_path

    except ImportError:
        raise RuntimeError("pydub is required for audio conversion. Install with: pip install pydub")
    except Exception as e:
        raise RuntimeError(f"Audio conversion failed: {str(e)}")


async def save_upload(content: bytes, filename: str) -> str:
    """Save uploaded audio bytes to a temporary file."""
    settings = get_settings()
    audio_dir = settings.data_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = Path(filename).name
    ext = Path(safe_name).suffix or ".webm"

    fd, temp_path = tempfile.mkstemp(suffix=ext, dir=str(audio_dir))
    with os.fdopen(fd, "wb") as f:
        f.write(content)

    logger.debug("audio_upload_saved", path=temp_path, size=len(content))
    return temp_path


def cleanup_temp_audio(path: str) -> None:
    """Remove a temporary audio file."""
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass
