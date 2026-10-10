#!/usr/bin/env bash
# ============================================================
# NOVA — macOS Setup Script
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}ℹ ${NC}$1"; }
ok()    { echo -e "${GREEN}✅ ${NC}$1"; }
warn()  { echo -e "${YELLOW}⚠️  ${NC}$1"; }
fail()  { echo -e "${RED}❌ ${NC}$1"; }

echo ""
echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      NOVA — macOS Setup Script       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
echo ""

# --- Check macOS ---
if [[ "$(uname)" != "Darwin" ]]; then
    fail "This script is designed for macOS."
    exit 1
fi
ok "macOS detected"

# --- Check Apple Silicon ---
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    ok "Apple Silicon ($ARCH)"
else
    warn "Non-Apple Silicon detected ($ARCH). Performance may vary."
fi

# --- Check Homebrew ---
if command -v brew &>/dev/null; then
    ok "Homebrew installed"
else
    warn "Homebrew not found. Install from https://brew.sh"
    echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
fi

# --- Check Python 3.10+ ---
PYTHON=""
for py in python3.11 python3.12 python3.10 python3; do
    if command -v "$py" &>/dev/null; then
        VERSION=$($py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [[ "$MAJOR" -ge 3 ]] && [[ "$MINOR" -ge 10 ]]; then
            PYTHON="$py"
            ok "Python $VERSION found ($py)"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    fail "Python 3.10+ not found."
    echo "  Install with: brew install python@3.11"
fi

# --- Check Node.js ---
if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version)
    ok "Node.js $NODE_VERSION"
else
    fail "Node.js not found."
    echo "  Install with: brew install node"
fi

# --- Check npm ---
if command -v npm &>/dev/null; then
    NPM_VERSION=$(npm --version)
    ok "npm $NPM_VERSION"
else
    fail "npm not found."
fi

# --- Check Ollama ---
if command -v ollama &>/dev/null; then
    ok "Ollama installed"
    if curl -s http://127.0.0.1:11434/ &>/dev/null; then
        ok "Ollama is running"
    else
        warn "Ollama is installed but not running. Start with: ollama serve"
    fi
else
    fail "Ollama not found."
    echo "  Install from: https://ollama.ai/download"
    echo "  Or: brew install ollama"
fi

# --- Check ffmpeg (for audio processing) ---
if command -v ffmpeg &>/dev/null; then
    ok "ffmpeg installed (for audio processing)"
else
    warn "ffmpeg not found. Required for voice features."
    echo "  Install with: brew install ffmpeg"
fi

# --- Setup Backend ---
echo ""
info "Setting up backend..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if [[ -n "$PYTHON" ]]; then
    if [[ ! -d "backend/.venv" ]]; then
        info "Creating Python virtual environment..."
        $PYTHON -m venv backend/.venv
        ok "Virtual environment created"
    else
        ok "Virtual environment exists"
    fi

    info "Installing backend dependencies..."
    backend/.venv/bin/pip install --upgrade pip -q
    backend/.venv/bin/pip install -r backend/requirements.txt -q
    ok "Backend dependencies installed"
fi

# --- Setup Frontend ---
echo ""
info "Setting up frontend..."

if [[ -d "frontend" ]]; then
    cd frontend
    if [[ ! -d "node_modules" ]]; then
        info "Installing frontend dependencies..."
        npm install
        ok "Frontend dependencies installed"
    else
        ok "Frontend dependencies exist"
    fi
    cd "$PROJECT_DIR"
fi

# --- Create .env if missing ---
if [[ ! -f ".env" ]]; then
    cp .env.example .env
    ok "Created .env from .env.example"
else
    ok ".env exists"
fi

# --- Create data directories ---
mkdir -p data/documents data/audio data/chroma logs
ok "Data directories ready"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        Setup Complete! 🎉            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo "  1. Pull an Ollama model:  ollama pull llama3.2:1b"
echo "  2. Start Ollama:          ollama serve"
echo "  3. Start NOVA:            ./scripts/start_all.sh"
echo ""
