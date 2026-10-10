"""Nova Voice Assistant Pipeline.

A self-contained voice-assistant pipeline that processes audio input
through VAD, transcription, validation, intent detection, command
planning/execution, and TTS output.

Usage:
    from nova import NovaPipeline

    pipeline = NovaPipeline()
    response = await pipeline.run(audio_bytes, sample_rate=16000)
"""

from nova.orchestrator import NovaPipeline

__all__ = ["NovaPipeline"]
__version__ = "0.1.0"
