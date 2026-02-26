@echo off
echo ================================================
echo Financial News Analysis Platform - Startup Script
echo ================================================

REM Set Python path to include src directory
set PYTHONPATH=%PYTHONPATH%;%~dp0src

REM Start FastAPI backend
echo Starting FastAPI backend server...
start cmd /k "cd src && python -m uvicorn financial_news.api.main:app --reload --host 0.0.0.0 --port 8000"
echo FastAPI backend started at http://localhost:8000

REM Wait a moment before starting frontend
timeout /t 3 /nobreak > nul

REM Start Next.js frontend
echo Starting Next.js frontend server...
start cmd /k "cd /d . && bun run dev"
echo Next.js frontend starting at http://localhost:3000

echo.
echo Both servers are starting up!
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Press Ctrl+C in the respective command windows to stop the servers.
