"""NOVA — Voice Routes."""

from __future__ import annotations

import os
import re

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import Optional

import structlog
from app.services.voice_service import transcribe_audio, voice_respond, speak_text
from app.schemas.voice import TranscribeResponse, SpeakRequest
from app.speech.wake_word import get_wake_word_detector

router = APIRouter(tags=["voice"])
logger = structlog.get_logger(__name__)


@router.post("/api/voice/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile = File(...)):
    """Transcribe uploaded audio to text."""
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Audio file too large (max 25MB)")

        result = await transcribe_audio(content, file.filename or "audio.webm")
        return TranscribeResponse(
            text=result["text"],
            language=result.get("language", "en"),
            confidence=result.get("confidence"),
            duration_ms=result.get("duration_ms", 0),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/api/voice/wake-check")
async def wake_check(file: UploadFile = File(...)):
    """
    Check if wake word is present in a short audio clip.
    Uses openWakeWord on-device model first, falling back to Whisper transcript if unavailable.
    Returns: {detected: bool, transcript: str, score: float}
    """
    try:
        content = await file.read()
        # Clips under 1KB are too short to contain speech
        if len(content) < 1000:
            return {"detected": False, "transcript": "", "score": 0.0}

        detector = get_wake_word_detector()
        if detector.is_available:
            result = detector.predict_clip(content, file.filename or "wake.webm")
            if result.get("detected", False):
                return {
                    "detected": True,
                    "transcript": result.get("model", "wake_word"),
                    "score": result.get("score", 0.0),
                }
            logger.info(
                "wake_word_not_detected_using_local_stt_fallback",
                score=result.get("score", 0.0),
                threshold=result.get("threshold", detector.threshold),
            )

        # Local STT fallback preserves the "Hey Nova" phrase because the
        # pretrained openWakeWord model is "hey_jarvis", not "hey_nova".
        stt_result = await transcribe_audio(content, file.filename or "wake.webm")
        text = stt_result.get("text", "").lower().strip()
        normalized_text = re.sub(r"[^a-z0-9]+", " ", text).strip()
        wake_variants = (
            "hey nova",
            "hi nova",
            "hey nora",
            "ok nova",
            "okay nova",
            "hey jarvis",
            "k nova",
            "knova",
        )
        detected = any(variant in normalized_text for variant in wake_variants)
        return {"detected": detected, "transcript": text, "score": 1.0 if detected else 0.0}

    except Exception as exc:
        logger.exception("wake_check_failed", error=str(exc))
        return {"detected": False, "transcript": "", "score": 0.0}


@router.post("/api/voice/respond")
async def respond(
    file: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None),
):
    """Full voice pipeline: audio in → text response + audio out."""
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")

        result = await voice_respond(content, file.filename or "audio.webm", conversation_id)

        response_data = {
            "message_id": result.get("message_id"),
            "conversation_id": result.get("conversation_id"),
            "transcript": result["transcript"],
            "response": result["response"],
            "agent_state": result.get("agent_state", "idle"),
            "stt_duration_ms": result.get("stt_duration_ms", 0),
            "llm_duration_ms": result.get("llm_duration_ms", 0),
            "tts_duration_ms": result.get("tts_duration_ms", 0),
            "total_latency_ms": result.get("total_latency_ms", 0),
            "has_audio": result.get("audio_path") is not None,
        }
        return response_data

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/api/voice/speak")
async def speak(request: SpeakRequest):
    """Convert text to speech audio."""
    try:
        audio_path = await speak_text(request.text)
        if audio_path and os.path.exists(audio_path):
            return FileResponse(
                audio_path,
                media_type="audio/wav",
                filename="nova_speech.wav",
            )
        raise HTTPException(status_code=503, detail="TTS failed to generate audio")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
