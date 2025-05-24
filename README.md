# Financial News - Advanced Analysis Platform

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A comprehensive financial news analysis and summarization platform powered by advanced AI and machine learning technologies.

## 🚀 Features

### Core Capabilities
- **Real-time News Aggregation**: Multi-source financial news collection and processing
- **Advanced Sentiment Analysis**: AI-powered sentiment analysis using transformer models
- **Intelligent Summarization**: Automatic article summarization and key insights extraction
- **Interactive Dashboard**: Modern web-based dashboard for visualization and monitoring
- **RESTful API**: Complete API for seamless integration with other systems
- **Command-line Interface**: Powerful CLI tools for automation and scripting

### Analysis Features
- **Multi-modal Sentiment Analysis**: Text, image, and video sentiment analysis
- **Entity Recognition**: Automatic extraction of companies, people, and financial instruments
- **Topic Modeling**: Intelligent categorization and topic extraction
- **Trend Analysis**: Historical trend analysis and pattern recognition
- **Real-time Streaming**: Live data processing and WebSocket streaming

## 📁 Project Structure

```
financenews/
├── src/financial_news/          # Main package
│   ├── config/                  # Configuration management
│   ├── core/                    # Core business logic
│   ├── models/                  # Data models and ML models
│   ├── services/                # External services and APIs
│   ├── api/                     # Web API layer
│   ├── cli/                     # Command-line interface
│   ├── dashboard/               # Interactive dashboard
│   └── utils/                   # Utility functions
├── tests/                       # Test suite
├── docs/                        # Documentation
├── scripts/                     # Development scripts
├── config/                      # Configuration files
└── deployment/                  # Deployment configurations
```

## 🛠️ Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Git

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd financenews
   ```

2. **Set up virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   # For production use
   pip install -e .
   
   # For development
   pip install -e ".[dev]"
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

5. **Run the application**
   ```bash
   # Start the dashboard
   make run-dashboard
   
   # Or start the API server
   make run-api
   
   # Or use the CLI
   make run-cli
   ```

## 🔧 Configuration

The application uses environment variables for configuration. Copy `.env.example` to `.env` and configure:

```bash
# API Keys
ALPHA_VANTAGE_API_KEY=your_key_here
FINNHUB_API_KEY=your_key_here
NEWS_API_KEY=your_key_here

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=financial_news

# Application
ENVIRONMENT=development
DEBUG=true
```

## 🚀 Usage

### Dashboard
Access the interactive dashboard at `http://localhost:8000` after running:
```bash
make run-dashboard
```

### API
Start the REST API server:
```bash
make run-api
```

API endpoints will be available at `http://localhost:8000/api/`

### CLI
Use the command-line interface:
```bash
# Analyze news sentiment
python -m financial_news.cli analyze --source "news_api" --symbol "AAPL"

# Generate summary
python -m financial_news.cli summarize --input "article.txt"

# Stream real-time data
python -m financial_news.cli stream --symbols "AAPL,GOOGL,MSFT"
```

### Python API
```python
from financial_news import get_settings, setup_logging
from financial_news.core.summarizer import NewsummarIzer
from financial_news.models.ml.sentiment import SentimentAnalyzer

# Initialize
settings = get_settings()
setup_logging(level="INFO")

# Use components
summarizer = NewsummarIzer()
analyzer = SentimentAnalyzer()

# Analyze sentiment
result = analyzer.analyze("Apple stock reaches new highs")
print(f"Sentiment: {result.sentiment}, Confidence: {result.confidence}")
```

## 🧪 Testing

Run the test suite:
```bash
# All tests
make test

# Unit tests only
make test-unit

# Integration tests only
make test-integration
```

## 🔍 Code Quality

The project uses automated code quality tools:

```bash
# Format code
make format

# Lint code
make lint

# Run pre-commit hooks
pre-commit run --all-files
```

## 📚 Documentation

- **Full Documentation**: [docs/index.md](docs/index.md)
- **API Reference**: [docs/api/](docs/api/)
- **User Guide**: [docs/user-guide/](docs/user-guide/)
- **Development Guide**: [docs/development/](docs/development/)

Build and serve documentation locally:
```bash
make docs
make serve-docs
```

## 🏗️ Development

### Development Setup
```bash
# Install development dependencies
make install-dev

# Set up pre-commit hooks
pre-commit install

# Run in development mode
make run-dashboard
```

### Project Commands
```bash
make help                 # Show all available commands
make install             # Install production dependencies
make install-dev         # Install development dependencies
make test                # Run all tests
make lint                # Run code linting
make format              # Format code
make clean               # Clean up cache files
make build               # Build the package
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](docs/development/contributing.md) for details.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Comprehensive guides and API reference
- **Issues**: [GitHub Issues](https://github.com/your-repo/issues) for bug reports and feature requests
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions) for questions and community support

## 🙏 Acknowledgments

- Built with modern Python best practices
- Powered by state-of-the-art transformer models
- Inspired by the open-source community

---

**Made with ❤️ by the Financial News Team** 