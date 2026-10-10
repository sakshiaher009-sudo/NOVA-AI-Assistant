"""Nova Pipeline — Orchestrator.

The single integration point for the entire voice-assistant pipeline.
External code only ever needs::

    from nova import NovaPipeline

    pipeline = NovaPipeline()
    response = await pipeline.run(audio_bytes, sample_rate=16000)

All internal wiring (VAD → STT → validate → intent → plan/execute/verify
→ respond → TTS) is handled here.
"""

from __future__ import annotations

import structlog

from nova.config import NovaConfig, get_config
from nova.interfaces import (
    AudioResponse,
    AudioSegment,
    IntentCategory,
    NovaResponse,
)
from nova.tools.base_tool import NovaTool
from nova.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)


class NovaPipeline:
    """End-to-end voice assistant pipeline.

    Processes raw audio through VAD, transcription, validation, intent
    detection, command planning/execution/verification, response building,
    and TTS synthesis.

    Args:
        config: Optional configuration override (defaults are read from
            environment variables with the ``NOVA_`` prefix).
        tools: Optional list of tools to register.  If not provided,
            the registry starts empty and tools can be added later via
            ``register_tool()``.

    Example::

        pipeline = NovaPipeline()
        pipeline.register_tool(MyCalculatorTool())

        # Full audio pipeline
        audio_response = await pipeline.run(audio_bytes)

        # Text-only pipeline (skip VAD & STT)
        text_response = await pipeline.run_text("What time is it?")
    """

    def __init__(
        self,
        config: NovaConfig | None = None,
        tools: list[NovaTool] | None = None,
    ) -> None:
        self.config = config or get_config()
        self.registry = ToolRegistry()

        if tools:
            for tool in tools:
                self.registry.register(tool)

        logger.info(
            "nova_pipeline_initialized",
            tools=self.registry.get_names(),
            model=self.config.ollama_model,
            tts_engine=self.config.tts_engine,
        )

    # ------------------------------------------------------------------
    # Tool management
    # ------------------------------------------------------------------

    def register_tool(self, tool: NovaTool) -> None:
        """Register a tool for use in COMMAND execution.

        Args:
            tool: The tool instance to register.
        """
        self.registry.register(tool)

    # ------------------------------------------------------------------
    # Full audio pipeline
    # ------------------------------------------------------------------

    async def run(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
    ) -> AudioResponse:
        """Run the full audio pipeline: audio → response audio.

        Args:
            audio_data: Raw 16-bit signed LE PCM audio data.
            sample_rate: Sample rate of the input audio in Hz.

        Returns:
            An ``AudioResponse`` with the synthesized reply audio.
        """
        from nova import vad, transcriber, tts

        logger.debug("nova_pipeline_run_start", audio_bytes=len(audio_data))

        # ── Stage 1: VAD ──────────────────────────────────────────────
        events = vad.detect_speech_segments(
            audio_data, sample_rate, config=self.config,
        )
        logger.debug("nova_pipeline_vad_done", segments=len(events))

        if not events:
            response = NovaResponse(
                text="I didn't detect any speech. Please try again.",
                success=True,
            )
            return await tts.synthesize(response, config=self.config)

        # ── Stage 2: Transcribe ───────────────────────────────────────
        # Use the longest speech segment for transcription
        longest = max(events, key=lambda e: e.end_ms - e.start_ms)
        segment = vad.extract_segment_audio(audio_data, longest, sample_rate)

        transcript = await transcriber.transcribe(segment, config=self.config)
        logger.debug(
            "nova_pipeline_transcript",
            text=transcript.text[:100],
            confidence=transcript.confidence,
        )

        # ── Stages 3–7: Text pipeline ────────────────────────────────
        nova_response = await self._process_text(transcript.text, transcript.confidence)

        # ── Stage 8: TTS ──────────────────────────────────────────────
        audio_response = await tts.synthesize(nova_response, config=self.config)
        logger.debug("nova_pipeline_run_complete", text=nova_response.text[:100])
        return audio_response

    # ------------------------------------------------------------------
    # Text-only pipeline
    # ------------------------------------------------------------------

    async def run_text(self, text: str) -> NovaResponse:
        """Run the text-only pipeline (skip VAD & STT).

        Useful for text chat input or testing without audio.

        Args:
            text: The user's text input.

        Returns:
            A ``NovaResponse`` with the assistant's reply.
        """
        logger.debug("nova_pipeline_run_text_start", text=text[:100])
        return await self._process_text(text, confidence=None)

    # ------------------------------------------------------------------
    # Core text processing (shared by run() and run_text())
    # ------------------------------------------------------------------

    async def _process_text(
        self,
        text: str,
        confidence: float | None,
    ) -> NovaResponse:
        """Process text through validation → intent → execution → response.

        Args:
            text: Transcript or direct text input.
            confidence: Transcription confidence (None for text input).

        Returns:
            A ``NovaResponse``.
        """
        from nova import validator, intent as intent_module, responder
        from nova.interfaces import Transcript

        # ── Stage 3: Validate ─────────────────────────────────────────
        transcript = Transcript(text=text, confidence=confidence)
        validation = validator.validate(transcript, config=self.config)

        logger.debug(
            "nova_pipeline_validation",
            status=validation.status.value,
            reason=validation.reason,
        )

        if not validation.is_clear:
            return responder.build_unclear_response(validation)

        # ── Stage 4: Intent Detection ─────────────────────────────────
        detected_intent = await intent_module.classify_intent(
            text, config=self.config,
        )
        logger.debug(
            "nova_pipeline_intent",
            category=detected_intent.category.value,
            confidence=detected_intent.confidence,
        )

        # ── Stage 5–7: Route by intent ────────────────────────────────
        if detected_intent.category in (IntentCategory.CHAT, IntentCategory.QUESTION):
            return await self._handle_conversation(detected_intent)
        elif detected_intent.category == IntentCategory.COMMAND:
            return await self._handle_command(detected_intent)
        else:
            # Should never happen — but just in case
            return responder.build_error_response(
                f"Unknown intent category: {detected_intent.category}"
            )

    # ------------------------------------------------------------------
    # CHAT / QUESTION path
    # ------------------------------------------------------------------

    async def _handle_conversation(self, intent_obj) -> NovaResponse:
        """Handle CHAT and QUESTION intents via LLM conversation."""
        from nova import llm_client, responder

        logger.debug("nova_pipeline_conversation", category=intent_obj.category.value)

        system_prompt = (
            "You are Nova, a helpful and friendly AI voice assistant. "
            "Keep your responses concise and conversational — they will be "
            "spoken aloud via text-to-speech. Avoid markdown formatting, "
            "code blocks, or overly long answers."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": intent_obj.raw_text},
        ]

        try:
            llm_response = await llm_client.chat(messages, config=self.config)
            return responder.build_chat_response(intent_obj, llm_response.content)
        except Exception as exc:
            logger.error("nova_conversation_failed", error=str(exc))
            return responder.build_error_response(str(exc))

    # ------------------------------------------------------------------
    # COMMAND path
    # ------------------------------------------------------------------

    async def _handle_command(self, intent_obj) -> NovaResponse:
        """Handle COMMAND intents: plan → execute → verify → respond."""
        from nova import planner, executor, verifier, responder

        logger.debug("nova_pipeline_command", text=intent_obj.raw_text[:80])

        # Check if any tools are available
        if len(self.registry) == 0:
            return responder.build_error_response(
                "No tools are registered. Cannot execute commands."
            )

        # ── Plan ──────────────────────────────────────────────────────
        plan = await planner.create_plan(
            intent_obj.raw_text,
            self.registry.get_schemas(),
            config=self.config,
        )

        if not plan.steps:
            # Planner couldn't match any tools — fall back to conversation
            logger.debug("nova_pipeline_no_plan_fallback")
            return await self._handle_conversation(intent_obj)

        logger.debug(
            "nova_pipeline_plan_created",
            steps=len(plan.steps),
            tools=[s.tool_name for s in plan.steps],
        )

        # ── Execute ───────────────────────────────────────────────────
        results = await executor.execute_plan(plan, self.registry)

        # ── Verify ────────────────────────────────────────────────────
        verifications = verifier.verify_all(plan.steps, results)

        logger.debug(
            "nova_pipeline_verified",
            all_passed=all(v.passed for v in verifications),
            results=len(results),
        )

        # ── Respond ───────────────────────────────────────────────────
        return responder.build_command_response(
            intent_obj, results, verifications,
        )
