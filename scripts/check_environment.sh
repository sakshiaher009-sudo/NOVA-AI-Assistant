#!/usr/bin/env bash
# ============================================================
# NOVA — Environment Check Script
# ============================================================
set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}NOVA — Environment Check${NC}"
echo "========================="
echo ""
 
# macOS version
echo -e "${BLUE}System:${NC}"
echo "  macOS: $(sw_vers -productVersion)"
echo "  CPU:   $(uname -m)"
echo "  RAM:   $(sysctl -n hw.memsize | awk '{print $1/1073741824 " GB"}')"
echo ""

# Python
echo -e "${BLUE}Python:${NC}"
for py in python3.11 python3.12 python3.10 python3; do
    if command -v "$py" &>/dev/null; then
        echo "  $py: $($py --version 2>&1)"
    fi
done
echo ""

# Node.js
echo -e "${BLUE}Node.js:${NC}"
if command -v node &>/dev/null; then
    echo "  Node: $(node --version)"
    echo "  npm:  $(npm --version)"
else
    echo -e "  ${RED}Not installed${NC}"
fi
echo ""

# Ollama
echo -e "${BLUE}Ollama:${NC}"
if command -v ollama &>/dev/null; then
    echo -e "  Installed: ${GREEN}Yes${NC}"
    if curl -s http://127.0.0.1:11434/ &>/dev/null; then
        echo -e "  Running:   ${GREEN}Yes${NC}"
        MODELS=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' | tr '\n' ', ' | sed 's/,$//')
        echo "  Models:    ${MODELS:-None}"
    else
        echo -e "  Running:   ${RED}No${NC}"
    fi
else
    echo -e "  Installed: ${RED}No${NC}"
fi
echo ""

# Backend
echo -e "${BLUE}Backend:${NC}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
if [[ -f "$PROJECT_DIR/backend/.venv/bin/python" ]]; then
    echo -e "  Venv:     ${GREEN}Ready${NC}"
else
    echo -e "  Venv:     ${RED}Not created${NC}"
fi
if curl -s http://127.0.0.1:8000/api/health &>/dev/null; then
    echo -e "  Server:   ${GREEN}Running${NC}"
else
    echo -e "  Server:   ${YELLOW}Not running${NC}"
fi
echo ""

# Frontend
echo -e "${BLUE}Frontend:${NC}"
if [[ -d "$PROJECT_DIR/frontend/node_modules" ]]; then
    echo -e "  Deps:     ${GREEN}Installed${NC}"
else
    echo -e "  Deps:     ${RED}Not installed${NC}"
fi
if curl -s http://127.0.0.1:3000 &>/dev/null; then
    echo -e "  Server:   ${GREEN}Running${NC}"
else
    echo -e "  Server:   ${YELLOW}Not running${NC}"
fi
echo ""

# Speech
echo -e "${BLUE}Speech:${NC}"
if command -v ffmpeg &>/dev/null; then
    echo -e "  ffmpeg:   ${GREEN}Available${NC}"
else
    echo -e "  ffmpeg:   ${RED}Not found (brew install ffmpeg)${NC}"
fi
if command -v say &>/dev/null; then
    echo -e "  macOS TTS:${GREEN}Available${NC}"
else
    echo -e "  macOS TTS:${RED}Not available${NC}"
fi
echo ""
