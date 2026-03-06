# Financial News Project Makefile
# Development task automation

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
PYTEST ?= .venv/bin/pytest
RUFF ?= .venv/bin/ruff
MYPY ?= .venv/bin/mypy

.PHONY: help install install-dev test test-unit test-integration lint typecheck format clean run run-api run-frontend coverage docker-up docker-down docker-build quality-checkpoint quality-ratchet staging-gate db-backup db-restore db-restore-drill

# Default target
help:
	@echo ""
	@echo "  Financial News — Development Commands"
	@echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "  Setup:"
	@echo "    install          Install production Python dependencies"
	@echo "    install-dev      Install development dependencies + pre-commit hooks"
	@echo ""
	@echo "  Development:"
	@echo "    run              Start everything (FastAPI + Next.js)"
	@echo "    run-api          Start FastAPI backend only"
	@echo "    run-frontend     Start Next.js frontend only (Bun)"
	@echo ""
	@echo "  Testing:"
	@echo "    test             Run all Python tests"
	@echo "    test-unit        Run unit tests only"
	@echo "    test-integration Run integration tests only"
	@echo "    coverage         Run tests with HTML coverage report"
	@echo ""
	@echo "  Code Quality:"
	@echo "    quality-checkpoint  Collect current quality metrics"
	@echo "    quality-ratchet     Enforce no-regression quality gate"
	@echo "    lint                Alias for quality-ratchet"
	@echo ""
	@echo "  Operations:"
	@echo "    staging-gate     Run migration/test/ratchet staging release gate"
	@echo "    db-backup        Create Postgres backup (DATABASE_URL)"
	@echo "    db-restore       Restore backup (BACKUP_FILE + RESTORE_DATABASE_URL)"
	@echo "    db-restore-drill Run timed backup+restore drill (DATABASE_URL + DRILL_DATABASE_URL)"
	@echo ""
	@echo "  Docker:"
	@echo "    docker-up        Start all services via Docker Compose"
	@echo "    docker-down      Stop all Docker services"
	@echo "    docker-build     Build Docker image"
	@echo ""
	@echo "  Other:"
	@echo "    clean            Remove caches and build artifacts"
	@echo ""

# Installation
install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"
	.venv/bin/pre-commit install

# Running
run:
	$(PYTHON) run_server.py

run-api:
	PYTHONPATH=src .venv/bin/uvicorn financial_news.api.main:app --reload --port 8000

run-frontend:
	bun run dev

# Testing
test:
	PYTHONPATH=src $(PYTEST) tests/ -v

test-unit:
	PYTHONPATH=src $(PYTEST) tests/unit/ -v

test-integration:
	PYTHONPATH=src $(PYTEST) tests/integration/ -v -m integration

coverage:
	PYTHONPATH=src $(PYTEST) tests/unit/ -v --cov=src/financial_news --cov-report=html --cov-report=term-missing
	@echo "\n  Coverage report: open htmlcov/index.html"

# Code quality
quality-checkpoint:
	$(PYTHON) scripts/quality_checkpoint.py collect --output-json output/quality/current.json --output-md output/quality/current.md

quality-ratchet: quality-checkpoint
	$(PYTHON) scripts/quality_checkpoint.py ratchet --baseline config/quality-baseline.json --current output/quality/current.json

lint: quality-ratchet

typecheck:
	bun run typecheck

format:
	$(RUFF) check src/ tests/ --fix
	$(RUFF) format src/ tests/

# Operations
staging-gate:
	PATH=".venv/bin:$$PATH" $(PYTHON) scripts/ops/staging_release_gate.py --output-json output/ops/staging-gate-report.json

db-backup:
	PATH=".venv/bin:$$PATH" $(PYTHON) scripts/ops/postgres_ops.py backup --database-url "$${DATABASE_URL}" --output-dir output/ops/backups --retention-days 7

db-restore:
	PATH=".venv/bin:$$PATH" $(PYTHON) scripts/ops/postgres_ops.py restore --backup-file "$${BACKUP_FILE}" --target-database-url "$${RESTORE_DATABASE_URL}" --recreate-target

db-restore-drill:
	PATH=".venv/bin:$$PATH" $(PYTHON) scripts/ops/postgres_ops.py drill --source-database-url "$${DATABASE_URL}" --target-database-url "$${DRILL_DATABASE_URL}" --output-json output/ops/restore-drill-report.json

# Docker
docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-build:
	docker build -t financenews:latest .

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ .coverage coverage.xml output/quality
	@echo "  Cleaned!"
