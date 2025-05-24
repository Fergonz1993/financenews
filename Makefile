# Financial News Project Makefile
# Development task automation

.PHONY: help install install-dev test test-unit test-integration lint format clean run-api run-dashboard run-cli docs serve-docs build

# Default target
help:
	@echo "Available commands:"
	@echo "  install       Install production dependencies"
	@echo "  install-dev   Install development dependencies"
	@echo "  test          Run all tests"
	@echo "  test-unit     Run unit tests only"
	@echo "  test-integration  Run integration tests only"
	@echo "  lint          Run code linting"
	@echo "  format        Format code with black and isort"
	@echo "  clean         Clean up cache and temporary files"
	@echo "  run-api       Start the API server"
	@echo "  run-dashboard Start the dashboard"
	@echo "  run-cli       Run the CLI interface"
	@echo "  docs          Build documentation"
	@echo "  serve-docs    Serve documentation locally"
	@echo "  build         Build the package"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

# Testing
test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

# Code quality
lint:
	flake8 src/ tests/
	mypy src/

format:
	black src/ tests/
	isort src/ tests/
	autoflake --in-place --remove-unused-variables --remove-all-unused-imports src/ tests/

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/

# Running applications
run-api:
	python -m financial_news.api.main

run-dashboard:
	python -m financial_news.dashboard.app

run-cli:
	python -m financial_news.cli.main

# Documentation
docs:
	mkdocs build

serve-docs:
	mkdocs serve

# Build
build:
	python -m build 