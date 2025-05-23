#!/usr/bin/env python3
"""
Financial News Summarizer Setup Script
Helps users configure the system and get started quickly.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def print_banner():
    """Print welcome banner."""
    print("""
╔═══════════════════════════════════════════════════╗
║        Financial News Summarizer Setup           ║
║              AI-Powered News Analysis             ║
╚═══════════════════════════════════════════════════╝
""")

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required.")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    print(f"✅ Python version: {sys.version}")

def create_env_file():
    """Create .env file from template."""
    env_template = Path("env_template")
    env_file = Path(".env")
    
    if env_file.exists():
        response = input("📝 .env file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("📄 Using existing .env file")
            return
    
    if env_template.exists():
        shutil.copy(env_template, env_file)
        print(f"📄 Created .env file from template")
        print("⚠️  Please edit .env file and add your API keys!")
    else:
        print("❌ Template file not found. Please create .env manually.")

def install_dependencies():
    """Install required dependencies."""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
    except subprocess.CalledProcessError:
        print("❌ Error installing dependencies")
        sys.exit(1)

def create_directories():
    """Create necessary directories."""
    directories = ["briefings", "cache", "logs", "data"]
    
    for dir_name in directories:
        dir_path = Path(dir_name)
        dir_path.mkdir(exist_ok=True)
        print(f"📁 Created directory: {dir_name}")

def test_configuration():
    """Test if configuration is valid."""
    print("\n🔍 Testing configuration...")
    
    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found")
        return False
    
    # Check for required API keys
    required_keys = ["OPENAI_API_KEY", "NEWS_API_KEY"]
    missing_keys = []
    
    with open(env_file) as f:
        content = f.read()
        for key in required_keys:
            if f"{key}=your_" in content:
                missing_keys.append(key)
    
    if missing_keys:
        print(f"❌ Missing API keys: {', '.join(missing_keys)}")
        print("   Please edit .env file and add your API keys")
        return False
    
    print("✅ Configuration looks good!")
    return True

def print_next_steps():
    """Print next steps for the user."""
    print("""
🎉 Setup Complete!

Next Steps:
1. Edit .env file and add your API keys:
   - Get OpenAI API key: https://platform.openai.com/api-keys
   - Get News API key: https://newsapi.org/register

2. Test the installation:
   python news_summarizer.py --config config.yaml

3. Run with specific stocks:
   python news_summarizer.py --queries AAPL MSFT "AI news"

4. For help and options:
   python news_summarizer.py --help

📚 Documentation: README.md
🐛 Issues: Please report any problems
""")

def main():
    """Main setup function."""
    print_banner()
    
    # Check system requirements
    check_python_version()
    
    # Setup process
    create_directories()
    install_dependencies()
    create_env_file()
    
    # Test configuration
    config_ok = test_configuration()
    
    # Final instructions
    print_next_steps()
    
    if not config_ok:
        print("⚠️  Remember to configure your API keys in .env file!")

if __name__ == "__main__":
    main() 