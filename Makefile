.PHONY: install setup dev backend frontend test lint format clean help

# ============================================================
# NOVA — Makefile
# ============================================================

PYTHON := python3
VENV := backend/.venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
UVICORN := $(VENV)/bin/uvicorn

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend ## Install all dependencies

install-backend: ## Install backend dependencies
	@echo "🔧 Setting up Python virtual environment..."
	cd backend && $(PYTHON) -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt
	@echo "✅ Backend dependencies installed"

install-frontend: ## Install frontend dependencies
	@echo "🔧 Installing frontend dependencies..."
	cd frontend && npm install
	@echo "✅ Frontend dependencies installed"

setup: install ## Full setup (install + env + data dirs)
	@cp -n .env.example .env 2>/dev/null || true
	@mkdir -p data/documents data/audio data/chroma logs
	@echo "✅ Setup complete. Edit .env to configure your models."

dev: ## Start both backend and frontend in development mode
	@./scripts/start_all.sh

backend: ## Start backend only
	cd backend && $(UVICORN) app.main:app --host 127.0.0.1 --port 8000 --reload

frontend: ## Start frontend only
	cd frontend && npm run dev

test: test-backend ## Run all tests

test-backend: ## Run backend tests
	cd backend && $(PYTEST) tests/ -v --tb=short

test-frontend: ## Run frontend tests
	cd frontend && npm test 2>/dev/null || echo "No frontend tests configured yet"

lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Lint backend
	cd backend && $(RUFF) check app/ tests/

lint-frontend: ## Lint frontend
	cd frontend && npm run lint

format: ## Format all code
	cd backend && $(RUFF) format app/ tests/
	cd frontend && npx prettier --write "app/**/*.{ts,tsx}" "components/**/*.{ts,tsx}" "lib/**/*.ts"

clean: ## Clean generated files
	rm -rf backend/.venv backend/__pycache__ backend/.pytest_cache
	rm -rf frontend/node_modules frontend/.next
	rm -rf data/app.db data/chroma logs/*.log
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned"

check: ## Check environment
	@./scripts/check_environment.sh

download-models: ## Download AI models
	@./scripts/download_models.sh
