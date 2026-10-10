"""NOVA — Backend Tests: Wake Word Detection."""

import io
import pytest
from pydub import AudioSegment
from app.speech.wake_word import WakeWordDetector, get_wake_word_detector


def _generate_wav_bytes(duration_ms: int = 1500) -> bytes:
    """Helper to generate dummy PCM WAV bytes."""
    seg = AudioSegment.silent(duration=duration_ms, frame_rate=16000)
    buf = io.BytesIO()
    seg.export(buf, format="wav")
    return buf.getvalue()


class TestWakeWordDetector:
    def test_detector_initialization(self):
        detector = get_wake_word_detector()
        assert detector.model_name == "hey_jarvis"
        assert detector.threshold == 0.5
        assert detector.is_available is True

    def test_predict_clip_silence(self):
        detector = get_wake_word_detector()
        wav_bytes = _generate_wav_bytes(1500)
        result = detector.predict_clip(wav_bytes, "test.wav")
        assert "detected" in result
        assert "score" in result
        assert isinstance(result["detected"], bool)
        # Pure silence shouldn't trigger wake word
        assert result["detected"] is False
        assert result["score"] < 0.5

    def test_predict_clip_too_short(self):
        detector = get_wake_word_detector()
        result = detector.predict_clip(b"short", "test.wav")
        assert result["detected"] is False
        assert result["reason"] == "clip_too_short"
