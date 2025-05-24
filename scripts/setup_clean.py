#!/usr/bin/env python3
"""
Clean Project Structure Setup
"""
import os
from pathlib import Path

def main():
    """Run the project setup."""
    
    # Create directories
    directories = [
        'src/financial_news',
        'src/financial_news/core', 
        'src/financial_news/models',
        'tests/integration',
        'docs',
        'config',
        'deployment'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Created: {directory}")
    
    # Create __init__.py files
    init_files = [
        'src/financial_news/__init__.py',
        'src/financial_news/core/__init__.py',
        'src/financial_news/models/__init__.py'
    ]
    
    for init_file in init_files:
        Path(init_file).touch()
        print(f"Created: {init_file}")
    
    print("\n✅ Basic project structure created!")
    print("Now you can manually move files to appropriate directories.")

if __name__ == "__main__":
    main() 