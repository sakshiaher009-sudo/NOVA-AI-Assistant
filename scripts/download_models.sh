#!/usr/bin/env bash
# ============================================================
# NOVA — Download Models Script
# ============================================================
set -euo pipefail

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${BLUE}NOVA — Model Download${NC}"
echo "====================="
echo ""

# Check Ollama
if ! command -v ollama &>/dev/null; then
    echo -e "${YELLOW}Ollama is not installed. Install from: https://ollama.ai/download${NC}"
    exit 1
fi

# Start Ollama if not running
if ! curl -s http://127.0.0.1:11434/ &>/dev/null; then
    echo -e "${YELLOW}Starting Ollama...${NC}"
    ollama serve &>/dev/null &
    sleep 3
fi

echo "Available model options:"
echo ""
echo "  Lightweight (~1.3GB, fast, good for M2 Air 8GB):"
echo "    ollama pull llama3.2:1b"
echo ""
echo "  Balanced (~2GB, better quality):"
echo "    ollama pull llama3.2:3b"
echo ""
echo "  Quality (~4.7GB, best quality, needs 16GB+ RAM):"
echo "    ollama pull llama3.1:8b"
echo ""

read -p "Which model to download? [llama3.2:1b]: " MODEL
MODEL=${MODEL:-llama3.2:1b}

echo ""
echo -e "${BLUE}Downloading $MODEL...${NC}"
ollama pull "$MODEL"
echo -e "${GREEN}✅ Model $MODEL downloaded successfully!${NC}"
echo ""
echo "Update your .env file:"
echo "  OLLAMA_MODEL=$MODEL"
echo ""
