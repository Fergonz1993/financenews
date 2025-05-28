#!/usr/bin/env python3
"""
Run script for the Financial News Analysis Platform.
This script ensures the proper Python path is set before starting the FastAPI server.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# Add the src directory to the Python path
current_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(current_dir / "src"))

def start_backend():
    """Start the FastAPI backend server."""
    os.chdir(current_dir)
    print("Starting FastAPI backend server...")
    try:
        # Use Python module mode to ensure proper imports
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "financial_news.api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
            cwd=str(current_dir / "src")
        )
        print("✅ FastAPI backend started at http://localhost:8000")
        # Give some time for the server to start
        time.sleep(2)
    except Exception as e:
        print(f"❌ Failed to start FastAPI backend: {e}")
        return False
    
    return True

def start_frontend():
    """Start the React frontend development server."""
    os.chdir(current_dir / "frontend")
    print("Starting React frontend server...")
    try:
        subprocess.Popen(
            ["npm", "start"],
            cwd=str(current_dir / "frontend")
        )
        print("✅ React frontend starting at http://localhost:3000")
    except Exception as e:
        print(f"❌ Failed to start React frontend: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("Financial News Analysis Platform - Startup Script")
    print("=" * 50)
    
    # Start the backend server
    backend_started = start_backend()
    
    if backend_started:
        # Start the frontend server
        frontend_started = start_frontend()
        
        if frontend_started:
            print("\nBoth servers are starting up!")
            print("Backend: http://localhost:8000")
            print("Frontend: http://localhost:3000")
            print("\nPress Ctrl+C to stop all servers.")
        else:
            print("Frontend server failed to start. Backend is running.")
    else:
        print("Backend server failed to start. Check the error messages above.")
