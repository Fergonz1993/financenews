#!/usr/bin/env python3
"""
Project Structure Setup Script
Reorganizes the financial news project into proper directory structure.
"""

import os
import shutil
from pathlib import Path

def create_project_structure():
    """Create proper project directory structure."""
    
    # Define directory structure
    directories = [
        'src/financial_news',
        'src/financial_news/core',
        'src/financial_news/agents', 
        'src/financial_news/data',
        'src/financial_news/models',
        'src/financial_news/utils',
        'tests/unit',
        'tests/integration',
        'tests/fixtures',
        'docs',
        'scripts',
        'config',
        'data/raw',
        'data/processed',
        'data/cache',
        'logs',
        'deployment/docker',
        'deployment/k8s',
        '.github/workflows'
    ]
    
    # Create directories
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")
    
    # Create __init__.py files for Python packages
    python_packages = [
        'src/financial_news',
        'src/financial_news/core',
        'src/financial_news/agents',
        'src/financial_news/data', 
        'src/financial_news/models',
        'src/financial_news/utils',
        'tests',
        'tests/unit',
        'tests/integration'
    ]
    
    for package in python_packages:
        init_file = Path(package) / '__init__.py'
        init_file.touch()
        print(f"✅ Created: {init_file}")

def move_files():
    """Move files to appropriate directories."""
    
    file_mappings = {
        # Core modules
        'enhanced_news_summarizer.py': 'src/financial_news/core/',
        'realtime_websocket_manager.py': 'src/financial_news/core/',
        'enhanced_graph_analyzer.py': 'src/financial_news/models/',
        'multimodal_sentiment_analyzer.py': 'src/financial_news/models/',
        'realtime_streaming_analyzer.py': 'src/financial_news/core/',
        'dashboard.py': 'src/financial_news/core/',
        
        # Tests
        'test_realtime_streams.py': 'tests/integration/',
        
        # Configuration
        'config.yaml': 'config/',
        'env_template': 'config/',
        
        # Documentation
        'README.md': 'docs/',
        'realtime_integration_plan.md': 'docs/',
        'QUICK_START_PHASE1.md': 'docs/',
        
        # Requirements
        'requirements_full.txt': './',
        'phase1_requirements.txt': './',
        'requirements.txt': './',
    }
    
    print("\n📦 Moving files to appropriate directories...")
    
    for source, destination in file_mappings.items():
        if os.path.exists(source):
            dest_path = Path(destination)
            dest_path.mkdir(parents=True, exist_ok=True)
            
            try:
                shutil.move(source, dest_path / Path(source).name)
                print(f"✅ Moved: {source} → {destination}")
            except Exception as e:
                print(f"❌ Failed to move {source}: {e}")
        else:
            print(f"⚠️  File not found: {source}")

def create_development_configs():
    """Create development configuration files."""
    
    configs = {
        # Pre-commit hooks
        '.pre-commit-config.yaml': '''
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-json
      - id: check-merge-conflict
      
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3
        
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=88, --extend-ignore=E203,W503]
        
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-PyYAML]
''',
        
        # PyProject.toml for modern Python packaging
        'pyproject.toml': '''
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "financial-news-ai"
version = "2.0.0"
description = "AI-powered Financial News Analysis with Real-time Streaming"
authors = [
    {name = "Financial News AI Team", email = "team@financialnews.ai"}
]
license = {text = "MIT"}
readme = "docs/README.md"
requires-python = ">=3.8"
keywords = ["finance", "news", "ai", "sentiment-analysis", "real-time"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Financial and Insurance Industry",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Topic :: Office/Business :: Financial",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]

dependencies = [
    "openai>=1.3.0",
    "websocket-client>=1.7.0",
    "websockets>=12.0",
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "rich>=13.6.0",
    "aiohttp>=3.9.0",
    "pandas>=2.1.0",
    "numpy>=1.24.0",
    "redis>=5.0.0",
    "python-dotenv>=1.0.0"
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-mock>=3.12.0",
    "black>=23.9.0",
    "flake8>=6.1.0",
    "mypy>=1.6.0",
    "pre-commit>=3.5.0"
]
ml = [
    "torch>=2.1.0",
    "torch-geometric>=2.4.0",
    "transformers>=4.35.0",
    "scikit-learn>=1.3.0"
]
full = [
    "financial-news-ai[dev,ml]",
]

[project.scripts]
financial-news = "financial_news.cli:main"

[project.urls]
Homepage = "https://github.com/yourusername/financial-news-ai"
Documentation = "https://financial-news-ai.readthedocs.io"
Repository = "https://github.com/yourusername/financial-news-ai.git"
Issues = "https://github.com/yourusername/financial-news-ai/issues"

[tool.black]
line-length = 88
target-version = ['py38']
include = '\\.pyi?$'
extend-exclude = '''
/(
  # directories
  \\.eggs
  | \\.git
  | \\.hg
  | \\.mypy_cache
  | \\.tox
  | \\.venv
  | build
  | dist
)/
'''

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true

[[tool.mypy.overrides]]
module = [
    "websocket.*",
    "finnhub.*",
    "yfinance.*",
    "redis.*"
]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "--verbose",
    "-ra"
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests"
]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/venv/*",
    "*/__pycache__/*"
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError"
]
''',
        
        # GitHub Actions CI
        '.github/workflows/ci.yml': '''
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, "3.10", "3.11"]

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
    
    - name: Lint with flake8
      run: |
        flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics
        flake8 src tests --count --exit-zero --max-complexity=10 --statistics
    
    - name: Type check with mypy
      run: mypy src
    
    - name: Test with pytest
      run: |
        pytest tests/ -v --cov=src --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  security:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Run security checks
      run: |
        pip install bandit safety
        bandit -r src/
        safety check
''',
        
        # Dockerfile
        'deployment/docker/Dockerfile': '''
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \\
    && apt-get install -y --no-install-recommends \\
        build-essential \\
        curl \\
        && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements_full.txt .
RUN pip install --no-cache-dir -r requirements_full.txt

# Copy project
COPY . .

# Install project in development mode
RUN pip install -e .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "financial_news.api:app", "--host", "0.0.0.0", "--port", "8000"]
''',
        
                 # Docker Compose for development         'deployment/docker/docker-compose.yml': '''version: '3.8'services:  app:    build:       context: ../..      dockerfile: deployment/docker/Dockerfile    ports:      - "8000:8000"    environment:      - REDIS_URL=redis://redis:6379      - DATABASE_URL=postgresql://postgres:password@postgres:5432/financial_news    depends_on:      - redis      - postgres    volumes:      - ../../logs:/app/logs      - ../../data:/app/data    restart: unless-stopped  redis:    image: redis:7-alpine    ports:      - "6379:6379"    volumes:      - redis_data:/data    restart: unless-stopped  postgres:    image: postgres:15    environment:      POSTGRES_DB: financial_news      POSTGRES_USER: postgres      POSTGRES_PASSWORD: password    ports:      - "5432:5432"    volumes:      - postgres_data:/var/lib/postgresql/data    restart: unless-stopped  nginx:    image: nginx:alpine    ports:      - "80:80"      - "443:443"    volumes:      - ./nginx.conf:/etc/nginx/nginx.conf    depends_on:      - app    restart: unless-stoppedvolumes:  redis_data:  postgres_data:'''
    }
    
    print("\n🔧 Creating development configuration files...")
    
    for filepath, content in configs.items():
        file_path = Path(filepath)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w') as f:
            f.write(content.strip())
        print(f"✅ Created: {filepath}")

def create_main_cli():
    """Create main CLI entry point."""
    
    cli_content = '''#!/usr/bin/env python3
"""
Financial News AI - Command Line Interface
Main entry point for the application.
"""

import asyncio
import click
from rich.console import Console

from financial_news.core.realtime_websocket_manager import RealTimeStreamManager
from financial_news.core.enhanced_news_summarizer import Config, CacheManager, EnhancedNewsSummarizer

console = Console()

@click.group()
@click.version_option(version="2.0.0")
def main():
    """Financial News AI - Real-time financial news analysis with AI."""
    pass

@main.command()
@click.option('--demo', is_flag=True, help='Run in demo mode with free APIs')
@click.option('--duration', default=300, help='Test duration in seconds')
def test(demo, duration):
    """Run real-time streaming test."""
    from tests.integration.test_realtime_streams import test_basic_functionality
    console.print("🚀 Starting real-time streaming test...")
    asyncio.run(test_basic_functionality())

@main.command()
def stream():
    """Start real-time news streaming."""
    from financial_news.core.realtime_websocket_manager import main as stream_main
    console.print("🌐 Starting real-time financial news streaming...")
    asyncio.run(stream_main())

@main.command()
@click.option('--host', default='0.0.0.0', help='Host to bind')
@click.option('--port', default=8000, help='Port to bind')
def api(host, port):
    """Start REST API server."""
    import uvicorn
    uvicorn.run(
        "financial_news.api:app",
        host=host,
        port=port,
        reload=True
    )

@main.command()
@click.argument('queries', nargs=-1)
@click.option('--output', default='console', help='Output format: console, json, markdown')
def analyze(queries, output):
    """Analyze financial news for given queries."""
    from financial_news.core.enhanced_news_summarizer import run_enhanced_summarizer
    
    if not queries:
        queries = ['AAPL', 'MSFT', 'GOOGL']
    
    console.print(f"📊 Analyzing news for: {', '.join(queries)}")
    asyncio.run(run_enhanced_summarizer(list(queries)))

if __name__ == "__main__":
    main()
'''
    
    cli_path = Path('src/financial_news/cli.py')
    cli_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(cli_path, 'w') as f:
        f.write(cli_content)
    
    print(f"✅ Created CLI entry point: {cli_path}")

if __name__ == "__main__":
    print("🏗️  Setting up proper project structure...")
    
    create_project_structure()
    create_development_configs()
    create_main_cli()
    
    print("\n🎉 Project structure setup complete!")
    print("\nNext steps:")
    print("1. Run: python project_structure_setup.py")
    print("2. Move files manually if needed")
    print("3. Install development dependencies: pip install -e '.[dev]'")
    print("4. Set up pre-commit: pre-commit install")
    print("5. Run tests: pytest") 