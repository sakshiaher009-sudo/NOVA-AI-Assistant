"""NOVA — On-Device Wake Word Detection via openWakeWord."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Optional

import numpy as np
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

_detector_instance: Optional[WakeWordDetector] = None


class WakeWordDetector:
    """On-device wake-word detection using openWakeWord with ONNX runtime."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
        threshold: Optional[float] = None,
    ):
        settings = get_settings()
        self.model_name = model_name or settings.wake_word_model
        self.model_path = model_path or settings.wake_word_model_path
        self.threshold = threshold if threshold is not None else settings.wake_word_threshold
        self.is_available = False
        self.model = None

        self._load_model()

    def _load_model(self) -> None:
        try:
            from openwakeword.model import Model

            if self.model_path and os.path.exists(self.model_path):
                model_source = str(Path(self.model_path).resolve())
            else:
                from openwakeword.utils import download_models

                download_models(model_names=[self.model_name])
                model_source = self.model_name

            logger.info("loading_wake_word_model", target=model_source, threshold=self.threshold)
            self.model = Model(wakeword_models=[model_source], inference_framework="onnx")
            self.is_available = True
            logger.info("wake_word_model_loaded", models=list(self.model.models.keys()))

        except Exception as e:
            logger.warning("wake_word_model_load_failed", error=str(e))
            self.is_available = False
            self.model = None

    def predict_clip(self, audio_bytes: bytes, filename: str = "wake.webm") -> dict:
        """
        Process an audio clip buffer and determine if wake word is present.
        Returns: {detected: bool, score: float, model: str}
        """
        if not self.is_available or self.model is None:
            return {"detected": False, "score": 0.0, "reason": "model_not_available"}

        if len(audio_bytes) < 1000:
            return {"detected": False, "score": 0.0, "reason": "clip_too_short"}

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

            # Convert uploaded audio to 16kHz mono 16-bit PCM
            seg = AudioSegment.from_file(io.BytesIO(audio_bytes))
            seg = seg.set_channels(1).set_frame_rate(16000).set_sample_width(2)
            samples = np.array(seg.get_array_of_samples(), dtype=np.int16)

            if len(samples) == 0:
                return {"detected": False, "score": 0.0}

            # Feed in 1280-sample (80ms) chunks to openWakeWord
            max_score = 0.0
            self.model.reset()

            for i in range(0, len(samples), 1280):
                chunk = samples[i : i + 1280]
                if len(chunk) < 1280:
                    chunk = np.pad(chunk, (0, 1280 - len(chunk)))
                prediction = self.model.predict(chunk)
                for score in prediction.values():
                    val = float(score)
                    if val > max_score:
                        max_score = val

            self.model.reset()
            detected = max_score >= self.threshold
            return {
                "detected": detected,
                "score": round(max_score, 4),
                "threshold": self.threshold,
                "model": self.model_name,
            }

        except Exception as e:
            logger.error("wake_word_prediction_error", error=str(e))
            return {"detected": False, "score": 0.0, "error": str(e)}


def get_wake_word_detector() -> WakeWordDetector:
    """Get or initialize singleton WakeWordDetector."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = WakeWordDetector()
    return _detector_instance


def set_wake_word_detector(detector: WakeWordDetector) -> None:
    """Set custom WakeWordDetector instance (useful for testing)."""
    global _detector_instance
    _detector_instance = detector
