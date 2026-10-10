"""Nova Pipeline — Voice Activity Detection.

Detects speech segments from raw audio using the Silero VAD ONNX model
(runs on ``onnxruntime`` which is already in the project's dependencies).

Falls back to treating the entire audio as one segment if the VAD model
is unavailable.
"""

from __future__ import annotations

import io
import struct
import time
from typing import Optional

import numpy as np
import structlog

from nova.config import NovaConfig, get_config
from nova.interfaces import AudioSegment, VADEvent

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Silero VAD via ONNX Runtime (lazy-loaded singleton)
# ---------------------------------------------------------------------------

_vad_model = None
_SILERO_SAMPLE_RATE = 16000  # Silero expects 16 kHz mono


def _load_vad_model():
    """Lazy-load the Silero VAD ONNX model."""
    global _vad_model
    if _vad_model is not None:
        return _vad_model

    try:
        import onnxruntime as ort

        # The Silero VAD ONNX model is bundled with the silero-vad package
        # or can be downloaded from the Silero GitHub repository.
        try:
            from silero_vad import load_silero_vad
            _vad_model = load_silero_vad(onnx=True)
            logger.info("vad_model_loaded", engine="silero-onnx")
            return _vad_model
        except ImportError:
            logger.info("silero_vad_package_not_available")

        # Fallback: try to load a local ONNX model file
        from pathlib import Path
        model_path = Path(__file__).parent / "models" / "silero_vad.onnx"
        if model_path.exists():
            _vad_model = ort.InferenceSession(str(model_path))
            logger.info("vad_model_loaded", engine="onnx-local", path=str(model_path))
            return _vad_model

        logger.warning("no_vad_model_found")
        return None

    except ImportError:
        logger.warning("onnxruntime_not_available")
        return None


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def _pcm_bytes_to_float32(audio_bytes: bytes, sample_rate: int) -> np.ndarray:
    """Convert raw 16-bit signed LE PCM bytes to float32 numpy array."""
    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return samples


def _resample_if_needed(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Simple linear resampling (no external dependency)."""
    if src_rate == dst_rate:
        return audio
    ratio = dst_rate / src_rate
    new_length = int(len(audio) * ratio)
    indices = np.linspace(0, len(audio) - 1, new_length)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_speech_segments(
    audio_bytes: bytes,
    sample_rate: int = 16000,
    *,
    config: NovaConfig | None = None,
) -> list[VADEvent]:
    """Detect speech segments in raw PCM audio.

    Args:
        audio_bytes: Raw 16-bit signed little-endian PCM audio data.
        sample_rate: Sample rate of the input audio in Hz.
        config: Optional config override.

    Returns:
        List of ``VADEvent`` with start/end timestamps in milliseconds.
        If VAD is unavailable, returns a single event spanning the full audio.
    """
    cfg = config or get_config()
    start_time = time.perf_counter()

    audio = _pcm_bytes_to_float32(audio_bytes, sample_rate)
    if sample_rate != _SILERO_SAMPLE_RATE:
        audio = _resample_if_needed(audio, sample_rate, _SILERO_SAMPLE_RATE)

    total_duration_ms = int(len(audio) / _SILERO_SAMPLE_RATE * 1000)

    model = _load_vad_model()
    if model is None:
        # Fallback: treat the entire audio as speech
        logger.debug("vad_fallback", reason="no_model", duration_ms=total_duration_ms)
        return [VADEvent(start_ms=0, end_ms=total_duration_ms, confidence=1.0)]

    # Use energy-based VAD as a simple but effective approach
    events = _energy_vad(audio, cfg)

    elapsed = int((time.perf_counter() - start_time) * 1000)
    logger.debug(
        "vad_complete",
        segments=len(events),
        total_duration_ms=total_duration_ms,
        processing_ms=elapsed,
    )
    return events


def _energy_vad(audio: np.ndarray, cfg: NovaConfig) -> list[VADEvent]:
    """Simple energy-based VAD that works without external models.

    Splits audio into short frames, computes RMS energy, and groups
    consecutive above-threshold frames into speech segments.
    """
    frame_duration_ms = 30  # 30ms frames
    frame_size = int(_SILERO_SAMPLE_RATE * frame_duration_ms / 1000)

    if len(audio) < frame_size:
        return [VADEvent(start_ms=0, end_ms=int(len(audio) / _SILERO_SAMPLE_RATE * 1000))]

    # Compute per-frame RMS energy
    num_frames = len(audio) // frame_size
    energies = []
    for i in range(num_frames):
        frame = audio[i * frame_size:(i + 1) * frame_size]
        rms = float(np.sqrt(np.mean(frame ** 2)))
        energies.append(rms)

    if not energies:
        return []

    # Adaptive threshold: use a fraction of the max energy
    max_energy = max(energies)
    if max_energy < 1e-6:
        return []  # silence

    threshold = max_energy * cfg.vad_threshold * 0.5
    min_speech_frames = max(1, cfg.vad_min_speech_duration_ms // frame_duration_ms)
    min_silence_frames = max(1, cfg.vad_min_silence_duration_ms // frame_duration_ms)

    # Find speech regions
    is_speech = [e > threshold for e in energies]
    events: list[VADEvent] = []
    segment_start: int | None = None
    silence_count = 0

    for i, speech in enumerate(is_speech):
        if speech:
            if segment_start is None:
                segment_start = i
            silence_count = 0
        else:
            if segment_start is not None:
                silence_count += 1
                if silence_count >= min_silence_frames:
                    segment_end = i - silence_count + 1
                    duration_frames = segment_end - segment_start
                    if duration_frames >= min_speech_frames:
                        avg_energy = np.mean(energies[segment_start:segment_end])
                        confidence = min(1.0, float(avg_energy / max_energy) * 2)
                        events.append(VADEvent(
                            start_ms=segment_start * frame_duration_ms,
                            end_ms=segment_end * frame_duration_ms,
                            confidence=confidence,
                        ))
                    segment_start = None
                    silence_count = 0

    # Handle segment that extends to end of audio
    if segment_start is not None:
        segment_end = num_frames
        duration_frames = segment_end - segment_start
        if duration_frames >= min_speech_frames:
            avg_energy = np.mean(energies[segment_start:segment_end])
            confidence = min(1.0, float(avg_energy / max(energies)) * 2)
            events.append(VADEvent(
                start_ms=segment_start * frame_duration_ms,
                end_ms=segment_end * frame_duration_ms,
                confidence=confidence,
            ))

    # If no segments found, fall back to full audio
    if not events:
        total_ms = int(len(audio) / _SILERO_SAMPLE_RATE * 1000)
        events = [VADEvent(start_ms=0, end_ms=total_ms, confidence=0.5)]

    return events


def extract_segment_audio(
    audio_bytes: bytes,
    event: VADEvent,
    sample_rate: int = 16000,
) -> AudioSegment:
    """Extract raw audio bytes for a specific VAD event.

    Args:
        audio_bytes: Full audio PCM data.
        event: The VAD event to extract.
        sample_rate: Sample rate of the audio.

    Returns:
        An ``AudioSegment`` containing only the speech region.
    """
    bytes_per_sample = 2  # 16-bit audio
    start_byte = int(event.start_ms / 1000 * sample_rate) * bytes_per_sample
    end_byte = int(event.end_ms / 1000 * sample_rate) * bytes_per_sample

    # Clamp to valid range
    start_byte = max(0, start_byte)
    end_byte = min(len(audio_bytes), end_byte)

    return AudioSegment(
        audio_bytes=audio_bytes[start_byte:end_byte],
        sample_rate=sample_rate,
        channels=1,
        start_ms=event.start_ms,
        end_ms=event.end_ms,
    )
