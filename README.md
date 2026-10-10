# NOVA — Local AI Voice Agent

<p align="center">
  <strong>A full-stack conversational AI voice assistant running entirely on your machine.</strong><br>
  Zero cloud costs. Zero API keys. 100% local.
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **🎙 Voice Conversations** | Record audio → local STT → AI response → local TTS |
| **💬 Text Chat** | Full conversational AI with context memory |
| **🧠 NLP Pipeline** | Intent classification + entity extraction (13 intents) |
| **📄 RAG Search** | Upload PDFs/docs → chunking → embeddings → semantic search |
| **📝 Notes** | Voice or text note creation, listing, deletion |
| **⏰ Reminders** | Date/time-aware reminder system |
| **🔧 Tool System** | Calculator, time, notes, reminders, document search |
| **📊 Analytics** | Conversation stats, latency metrics, intent distribution |
| **🌙 Modern UI** | Dark mode, responsive design, voice visualizer |
| **🔒 Privacy First** | All data stays on your machine |

## 🏗 Architecture

```
Browser ──→ Next.js Frontend ──→ FastAPI Backend
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
              Speech-to-Text     Agent Orchestrator    RAG System
              (faster-whisper)         │              (ChromaDB)
                    │           ┌──────┴──────┐          │
                    │           │             │          │
                    │      NLP Pipeline    Tool System   │
                    │           │             │          │
                    │           └──────┬──────┘          │
                    │                  │                  │
                    │            Local LLM (Ollama)       │
                    │                  │                  │
                    └──────────────────┼──────────────────┘
                                       │
                                 Text-to-Speech
                          (Piper / macOS say / Windows SAPI5)
```

**Persistent Storage:**
- SQLite → conversations, messages, notes, reminders, settings
- ChromaDB → document chunks + embeddings

## 📋 Requirements

### macOS
- macOS (Apple Silicon recommended)
- Python 3.10+, Node.js 18+, and Ollama
- FFmpeg on `PATH` for voice audio conversion (`brew install ffmpeg`)
- macOS `say` and `afconvert` are used for built-in speech output.

### Windows
- 64-bit Windows 10/11, Python 3.10+ (enable **Add Python to PATH**), and Node.js 18+
- Ollama for Windows, with a model downloaded locally
- FFmpeg available on `PATH` for voice audio conversion. For example, install with `winget install --id Gyan.FFmpeg --exact`, then reopen Command Prompt.
- Windows built-in SAPI5 speech is used for audio output through the `pyttsx3` Python package installed by the Windows dependency marker. No separate audio SDK is required. Microphone access must be allowed for the browser.

## 🚀 Installation and execution

### macOS

```bash
git clone <repo-url>
cd NOVA-AI-Assistant
./scripts/setup_mac.sh
ollama pull llama3.2:1b
./scripts/start_all.sh
```

The setup script installs the existing Python backend and Next.js frontend dependencies and creates `.env` from `.env.example` if needed. Start Ollama through its app or run `ollama serve` in another Terminal window if it is not already running. Set `OLLAMA_MODEL` in `.env` if you pulled a different model. The macOS launch script remains `scripts/start_all.sh`.

### Windows 10/11

Install Python, Node.js, Ollama, and FFmpeg first. The Python installer must add Python to `PATH`; after installing Ollama or FFmpeg, reopen Command Prompt so their commands are on `PATH`.

```bat
git clone <repo-url>
cd NOVA-AI-Assistant
scripts\setup_windows.bat
ollama pull llama3.2:1b
scripts\start_nova_windows.bat
```

The setup script checks required tools, installs backend and frontend dependencies, and creates a local `.env` with Windows SAPI5 selected when absent. If you already have a `.env` from another operating system, set `TTS_ENGINE=windows` in it. `pyttsx3` uses Windows SAPI5 for speech output. If you use another Ollama model, update `OLLAMA_MODEL` in `.env` to match. The launcher starts Ollama if its local service is not responding, then opens backend and frontend command windows. Open http://127.0.0.1:3000; API documentation is at http://127.0.0.1:8000/docs. Close the backend and frontend windows to stop NOVA.

### Ollama models

Choose a model appropriate for your available memory, then run the pull command on either OS:

```bash
ollama pull llama3.2:1b   # lightweight
ollama pull llama3.2:3b   # balanced
ollama pull llama3.1:8b   # larger; allow several GB of disk space
```

On macOS, from the repository root:

```bash
make test
make lint
```

On Windows, from the repository root:

```bat
backend\.venv\Scripts\python.exe -m pytest backend\tests\ -v --tb=short
```

## 🎯 NLP Pipeline

NOVA uses a multi-stage NLP pipeline:

```
Raw Text → Normalization → Language Detection → Intent Classification → Entity Extraction
```

### Supported Intents

| Intent | Example |
|--------|---------|
| `GENERAL_CONVERSATION` | "Hello, how are you?" |
| `QUESTION_ANSWERING` | "What is machine learning?" |
| `CALCULATE` | "What is 987 * 43?" |
| `GET_TIME` | "What time is it?" |
| `CREATE_NOTE` | "Remember that I need to study DBMS tonight" |
| `LIST_NOTES` | "Show my notes" |
| `DELETE_NOTE` | "Delete the note about databases" |
| `CREATE_REMINDER` | "Remind me tomorrow at 7 PM to practice Python" |
| `DOCUMENT_SEARCH` | "Find support vector machines in my PDF" |
| `DOCUMENT_SUMMARY` | "Summarize this document" |
| `SEARCH_MEMORY` | "What did I tell you about databases?" |
| `SYSTEM_STATUS` | "System status" |

### Entity Extraction

Extracts: dates, times, numbers, math expressions, tasks, topics, document references, durations.

## 📄 RAG System

Upload documents (PDF, TXT, MD, DOCX) → NOVA extracts text, chunks it, generates embeddings, and stores them in ChromaDB for semantic search.

```
Upload → Extract Text → Chunk → Embed → Store → Search → Answer with Citations
```

- **Embedding model:** `all-MiniLM-L6-v2` (~22MB)
- **Vector DB:** ChromaDB (local, persistent)
- **Chunk size:** 512 chars with 50 char overlap

## 🔧 Tool System

| Tool | Trigger |
|------|---------|
| Calculator | Math expressions, "calculate" |
| Time | "what time", "what date" |
| Create Note | "remember", "save note" |
| List Notes | "show notes", "my notes" |
| Delete Note | "delete note" |
| Create Reminder | "remind me" |
| Document Search | "find in document", "search PDF" |

Tools are safe — no arbitrary code execution, no shell commands.

## 🎙 Voice Pipeline

1. Browser records audio via MediaRecorder API
2. Audio sent to backend as WebM
3. Converted to WAV (16kHz mono)
4. Transcribed by faster-whisper or whisper
5. Processed through NLP pipeline
6. Agent generates response via local LLM
7. Response converted to speech via Piper or macOS `say`
8. Audio played in browser

## 🗄 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/status` | System status |
| POST | `/api/chat` | Text chat |
| POST | `/api/voice/transcribe` | Audio → text |
| POST | `/api/voice/respond` | Full voice pipeline |
| POST | `/api/voice/speak` | Text → audio |
| GET/POST | `/api/conversations` | Conversation CRUD |
| GET/DELETE | `/api/conversations/{id}` | Single conversation |
| POST | `/api/documents/upload` | Upload document |
| GET/DELETE | `/api/documents` | Document management |
| GET/POST/DELETE | `/api/notes` | Notes CRUD |
| GET/POST/PUT/DELETE | `/api/reminders` | Reminders CRUD |
| GET/POST/DELETE | `/api/memory` | Memory management |
| GET | `/api/analytics` | Analytics dashboard |

## 🔒 Security

- Input validation on all endpoints
- File upload restrictions (type, size)
- Path traversal protection
- No arbitrary code execution
- No shell command access from LLM
- CORS configured for local development
- Secrets kept in `.env` (not committed)

## ⚡ Performance

- Lazy model loading (STT/TTS/embeddings loaded on first use)
- Model caching (singleton instances)
- Streaming LLM support
- Temporary audio file cleanup
- Configurable context window size
- Batch embedding generation

## 📁 Project Structure

```
nova/
├── backend/           # FastAPI Python backend
│   ├── app/
│   │   ├── api/       # Route handlers
│   │   ├── agent/     # Orchestrator, prompts, context, memory
│   │   ├── nlp/       # Intent, entities, preprocessing
│   │   ├── llm/       # Ollama client
│   │   ├── speech/    # STT, TTS, audio utilities
│   │   ├── rag/       # Document ingestion, chunking, embeddings
│   │   ├── tools/     # Calculator, time, notes, reminders
│   │   ├── database/  # SQLAlchemy models, repositories
│   │   ├── schemas/   # Pydantic models
│   │   └── services/  # Business logic
│   └── tests/
├── frontend/          # Next.js TypeScript frontend
│   └── app/           # Pages (chat, documents, notes, etc.)
├── scripts/           # Setup, start, check scripts
├── data/              # Runtime data (DB, vectors, uploads)
├── docs/              # Documentation
└── logs/              # Application logs
```

## 🔮 Future Improvements

- [ ] WebSocket streaming for real-time chat
- [ ] Multi-language support
- [ ] Piper TTS binary auto-download
- [ ] Voice activity detection
- [ ] Conversation summarization
- [ ] Plugin system for custom tools
- [ ] Export conversations
- [ ] Scheduled reminder notifications

## 📝 License

MIT License — see [LICENSE](LICENSE).
