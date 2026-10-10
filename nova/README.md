# Nova Voice Assistant Pipeline

A self-contained voice-assistant pipeline module for the NOVA project.  
Processes audio input through VAD → STT → Validation → Intent Detection → Execution → TTS.

## Architecture

```
🎤 Audio Stream
    │
    ▼
┌──────────┐     ┌──────────────────┐     ┌─────────────┐
│   VAD    │ ──▶ │  faster-whisper  │ ──▶ │  Validator   │
│ (speech  │     │  (transcribe)    │     │ (CLEAR /     │
│ segments)│     │                  │     │  UNCLEAR)    │
└──────────┘     └──────────────────┘     └──────┬──────┘
                                                  │
                              ┌────────────────────┴─────────────────┐
                              │                                      │
                         UNCLEAR                                  CLEAR
                              │                                      │
                    ┌─────────▼──────────┐              ┌────────────▼───────────┐
                    │  "Please repeat"   │              │   Intent Detection     │
                    │  (short-circuit)   │              │  CHAT|QUESTION|COMMAND  │
                    └─────────┬──────────┘              └────────────┬───────────┘
                              │                                      │
                              │                  ┌───────────────────┼──────────┐
                              │              CHAT/QUESTION        COMMAND       │
                              │                  │                    │         │
                              │           ┌──────▼──────┐    ┌───────▼───────┐ │
                              │           │  LLM Chat   │    │ Plan→Execute  │ │
                              │           │  Response    │    │   →Verify     │ │
                              │           └──────┬──────┘    └───────┬───────┘ │
                              │                  └────────┬──────────┘         │
                              │                           │                    │
                              │                  ┌────────▼─────────┐          │
                              └──────────────────▶  Nova Response   ◀──────────┘
                                                 └────────┬─────────┘
                                                          │
                                                   ┌──────▼──────┐
                                                   │     TTS     │
                                                   └──────┬──────┘
                                                          │
                                                       🔊 Audio
```

## Quick Start

```python
from nova import NovaPipeline

# Initialize the pipeline
pipeline = NovaPipeline()

# Full audio pipeline (audio bytes → audio response)
response = await pipeline.run(audio_bytes, sample_rate=16000)
print(response.audio_path)       # Path to generated WAV file
print(response.nova_response.text)  # The response text

# Text-only pipeline (skip VAD & STT)
text_response = await pipeline.run_text("What time is it?")
print(text_response.text)
print(text_response.success)
```

## Adding Tools

Tools enable the COMMAND pipeline path. Create a tool by extending `NovaTool`:

```python
from nova.tools.base_tool import NovaTool
from nova.interfaces import ToolResult, ToolParameter

class CalculatorTool(NovaTool):
    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Evaluate a math expression"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="expression",
                type="string",
                description="The math expression to evaluate",
                required=True,
            ),
        ]

    async def execute(self, params: dict) -> ToolResult:
        expr = params["expression"]
        try:
            result = eval(expr)  # Use a safe evaluator in production!
            return ToolResult(success=True, result=result, display_text=f"{expr} = {result}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

# Register with the pipeline
pipeline = NovaPipeline()
pipeline.register_tool(CalculatorTool())
```

## Configuration

All settings are read from environment variables with the `NOVA_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `NOVA_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama API server URL |
| `NOVA_OLLAMA_MODEL` | `llama3.2:1b` | LLM model name |
| `NOVA_OLLAMA_TIMEOUT` | `120` | HTTP timeout (seconds) |
| `NOVA_STT_MODEL` | `base` | Whisper model size |
| `NOVA_STT_DEVICE` | `cpu` | STT device (cpu/cuda) |
| `NOVA_STT_COMPUTE_TYPE` | `int8` | Compute type |
| `NOVA_TTS_ENGINE` | `macos` | TTS engine (macos/piper) |
| `NOVA_TTS_SPEED` | `1.0` | Speech rate multiplier |
| `NOVA_VAD_THRESHOLD` | `0.5` | VAD speech threshold |
| `NOVA_VALIDATOR_MIN_CONFIDENCE` | `0.4` | Minimum STT confidence |
| `NOVA_VALIDATOR_MIN_LENGTH` | `2` | Minimum transcript chars |
| `NOVA_LOG_LEVEL` | `INFO` | Logging level |

Or pass a custom config:

```python
from nova.config import NovaConfig

config = NovaConfig(ollama_model="llama3.1:8b", tts_engine="piper")
pipeline = NovaPipeline(config=config)
```

## Module Structure

```
nova/
├── __init__.py          # Exports NovaPipeline
├── config.py            # NOVA_* environment config
├── interfaces.py        # All typed dataclasses & enums
├── orchestrator.py      # NovaPipeline — single integration point
├── vad.py               # Voice Activity Detection
├── transcriber.py       # faster-whisper / whisper STT
├── validator.py         # CLEAR / UNCLEAR decision
├── intent.py            # LLM intent classifier (CHAT|QUESTION|COMMAND)
├── planner.py           # Command → ordered tool-call plan
├── executor.py          # Dispatches plan steps to tools
├── verifier.py          # Post-execution result verification
├── responder.py         # Builds unified NovaResponse
├── tts.py               # Text-to-speech (macOS say / Piper)
├── llm_client.py        # Standalone Ollama async HTTP client
├── tools/
│   ├── base_tool.py     # NovaTool abstract base class
│   └── registry.py      # ToolRegistry (instance-based, no globals)
└── tests/               # Unit tests (pytest)
```

## Data Flow

Every stage communicates via typed objects defined in `interfaces.py`:

```
bytes          → VADEvent       → AudioSegment    → Transcript
Transcript     → ValidationResult
                    ├─ UNCLEAR  → NovaResponse (clarification)
                    └─ CLEAR    → Intent
Intent                             ├─ CHAT/QUESTION → LLM → NovaResponse
                                   └─ COMMAND       → ExecutionPlan → ToolResult[]
                                                    → VerificationResult[] → NovaResponse
NovaResponse   → AudioResponse (via TTS)
```

## Running Tests

```bash
python -m pytest nova/tests/ -v
```

## New Dependencies

| Package | Purpose | Status |
|---------|---------|--------|
| `faster-whisper` | STT engine | Already used (verify version) |
| `numpy` | Audio array ops | Already installed |
| `httpx` | Ollama HTTP client | Already installed |
| `pydantic-settings` | Config management | Already installed |
| `structlog` | Structured logging | Already installed |
| `silero-vad` | VAD (optional upgrade) | **New — optional** |
