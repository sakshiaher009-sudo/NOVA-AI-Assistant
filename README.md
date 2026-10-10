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
                               (Piper / macOS say)
```

**Persistent Storage:**
- SQLite → conversations, messages, notes, reminders, settings
- ChromaDB → document chunks + embeddings

## 📋 Requirements

- **macOS** (Apple Silicon M1/M2 recommended)
- **Python 3.10+** (`brew install python@3.11`)
- **Node.js 18+** (`brew install node`)
- **Ollama** (https://ollama.ai/download)
- **ffmpeg** (for audio processing: `brew install ffmpeg`)

## 🚀 Installation

### 1. Clone and setup

```bash
git clone <repo-url>
cd nova

# Automated setup (recommended)
./scripts/setup_mac.sh

# Or manual setup
make setup
```

### 2. Pull an LLM model

```bash
# Start Ollama
ollama serve

# Pull a model (choose one)
ollama pull llama3.2:1b    # Lightweight (~1.3GB, good for 8GB RAM)
ollama pull llama3.2:3b    # Balanced (~2GB)
ollama pull llama3.1:8b    # Quality (~4.7GB, needs 16GB+ RAM)
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env to set your chosen model:
# OLLAMA_MODEL=llama3.2:1b
```

### 4. Start NOVA

```bash
# Start everything
./scripts/start_all.sh

# Or individually
make backend    # http://127.0.0.1:8000
make frontend   # http://127.0.0.1:3000
```

### 5. Open in browser

- **Frontend:** http://127.0.0.1:3000
- **API Docs:** http://127.0.0.1:8000/docs

## 🧪 Testing

```bash
make test           # Run all tests
make lint           # Lint all code
make test-backend   # Backend only
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
