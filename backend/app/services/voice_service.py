"""NOVA — Voice Service."""

from __future__ import annotations

import time
from typing import Optional

import structlog

from app.speech import stt, tts, audio
from app.agent.orchestrator import process_message

logger = structlog.get_logger(__name__)


async def transcribe_audio(audio_bytes: bytes, filename: str) -> dict:
    """Transcribe uploaded audio to text."""
    # Save uploaded audio
    temp_path = await audio.save_upload(audio_bytes, filename)

    try:
        # Convert to WAV if needed
        if not temp_path.endswith(".wav"):
            wav_path = await audio.convert_to_wav(temp_path)
            audio.cleanup_temp_audio(temp_path)
            temp_path = wav_path

        # Transcribe
        result = await stt.transcribe(temp_path)
        return result

    finally:
        audio.cleanup_temp_audio(temp_path)


async def voice_respond(
    audio_bytes: bytes,
    filename: str,
    conversation_id: Optional[str] = None,
) -> dict:
    """Full voice pipeline: audio → text → agent → speech."""
    total_start = time.perf_counter()

    # 1. Transcribe
    stt_start = time.perf_counter()
    transcript = await transcribe_audio(audio_bytes, filename)
    stt_ms = int((time.perf_counter() - stt_start) * 1000)

    text = transcript.get("text", "").strip()
    if not text:
        return {
            "transcript": "",
            "response": "I didn't catch that. Could you try again?",
            "audio_path": None,
            "stt_duration_ms": stt_ms,
        }

    # 2. Process through agent
    chat_response = await process_message(
        message=text,
        conversation_id=conversation_id,
        is_voice=True,
    )

    # 3. Generate speech
    tts_start = time.perf_counter()
    audio_path = None
    try:
        audio_path = await tts.synthesize(chat_response.response)
    except Exception as e:
        logger.warning("tts_failed", error=str(e))
    tts_ms = int((time.perf_counter() - tts_start) * 1000)

    total_ms = int((time.perf_counter() - total_start) * 1000)

    return {
        "message_id": chat_response.message_id,
        "conversation_id": chat_response.conversation_id,
        "transcript": text,
        "response": chat_response.response,
        "audio_path": audio_path,
        "agent_state": chat_response.agent_state,
        "stt_duration_ms": stt_ms,
        "llm_duration_ms": chat_response.llm_duration_ms,
        "tts_duration_ms": tts_ms,
        "total_latency_ms": total_ms,
    }


async def speak_text(text: str) -> str:
    """Convert text to speech, return audio file path."""
    return await tts.synthesize(text)
