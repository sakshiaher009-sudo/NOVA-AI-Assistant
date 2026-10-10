#!/usr/bin/env bash
# NOVA — Run Tests
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "Running backend tests..."
cd backend && .venv/bin/python -m pytest tests/ -v --tb=short
echo ""
echo "✅ All tests passed"
