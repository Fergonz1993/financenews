#!/usr/bin/env python3
"""
Financial News AI - Command Line Interface
Main entry point for the application.
"""

import asyncio

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(version="2.0.0")
def main():
    """Financial News AI - Real-time financial news analysis with AI."""
    pass


@main.command()
@click.option("--demo", is_flag=True, help="Run in demo mode with free APIs")
@click.option("--duration", default=300, help="Test duration in seconds")
def test(demo, duration):
    """Run real-time streaming test."""
    try:
        from tests.integration.test_realtime_streams import test_basic_functionality

        console.print("🚀 Starting real-time streaming test...")
        asyncio.run(test_basic_functionality())
    except ImportError as e:
        console.print(f"❌ Error importing test: {e}")
        console.print(
            "💡 Make sure you're in the project directory and have installed dependencies"
        )


@main.command()
def stream():
    """Start real-time news streaming."""
    try:
        from financial_news.core.realtime_websocket_manager import main as stream_main

        console.print("🌐 Starting real-time financial news streaming...")
        asyncio.run(stream_main())
    except ImportError as e:
        console.print(f"❌ Error importing stream manager: {e}")
        console.print(
            "💡 Make sure you're in the project directory and have installed dependencies"
        )


@main.command()
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", default=8000, help="Port to bind")
def api(host, port):
    """Start REST API server."""
    try:
        import uvicorn

        uvicorn.run("financial_news.api:app", host=host, port=port, reload=True)
    except ImportError:
        console.print("❌ uvicorn not installed. Install with: pip install uvicorn")


@main.command()
@click.argument("queries", nargs=-1)
@click.option(
    "--output", default="console", help="Output format: console, json, markdown"
)
def analyze(queries, output):
    """Analyze financial news for given queries."""
    try:
        from financial_news.core.enhanced_news_summarizer import run_enhanced_summarizer

        if not queries:
            queries = ["AAPL", "MSFT", "GOOGL"]

        console.print(f"📊 Analyzing news for: {', '.join(queries)}")
        asyncio.run(run_enhanced_summarizer(list(queries)))
    except ImportError as e:
        console.print(f"❌ Error importing analyzer: {e}")
        console.print(
            "💡 Make sure you're in the project directory and have installed dependencies"
        )


@main.command()
def setup():
    """Set up development environment."""
    console.print("🛠️ Setting up development environment...")

    # Check if we're in virtual environment
    import sys

    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        console.print("✅ Virtual environment detected")
    else:
        console.print(
            "⚠️ No virtual environment detected. Consider using: python -m venv venv"
        )

    console.print("📦 Install dependencies with: pip install -e .[dev]")
    console.print("🔧 Set up pre-commit with: pre-commit install")
    console.print("🧪 Run tests with: pytest")


if __name__ == "__main__":
    main()
