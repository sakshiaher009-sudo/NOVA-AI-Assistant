#!/usr/bin/env bash
# ============================================================
# NOVA — Start All Services
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

cleanup() {
    echo ""
    echo -e "${BLUE}Shutting down NOVA...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}NOVA stopped.${NC}"
}
trap cleanup EXIT INT TERM

# Create data dirs
mkdir -p data/documents data/audio data/chroma logs

# Create .env if missing
if [[ ! -f ".env" ]]; then
    cp .env.example .env
fi

# Start backend
echo -e "${BLUE}Starting NOVA backend...${NC}"
cd backend
# Pinned to --workers 1: ChromaDB runs with embedded SQLite persistence in data/chroma,
# which does not support multi-process concurrent writes.
# For multi-worker deployments, launch ChromaDB server separately:
#   chroma run --path ./data/chroma --port 8001
# and connect via chromadb.HttpClient(host="127.0.0.1", port=8001) in vector_store.py.
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --reload &
BACKEND_PID=$!
cd "$PROJECT_DIR"

# Wait for backend to be ready
sleep 2

# Start frontend
echo -e "${BLUE}Starting NOVA frontend...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd "$PROJECT_DIR"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          NOVA is running! 🚀             ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Frontend:  http://127.0.0.1:3000        ║${NC}"
echo -e "${GREEN}║  Backend:   http://127.0.0.1:8000        ║${NC}"
echo -e "${GREEN}║  API Docs:  http://127.0.0.1:8000/docs   ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Press Ctrl+C to stop                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

wait
