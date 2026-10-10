"""NOVA — Voice Manager."""

from __future__ import annotations

from app.speech import stt, tts


def get_voice_status() -> dict:
    """Return status of voice subsystems."""
    return {
        "stt_available": stt.is_available(),
        "tts_available": tts.is_available(),
    }
