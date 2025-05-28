@echo off
echo Starting Financial News Analysis Platform...

:: Create necessary directories
mkdir -p data\saved_articles

:: Start FastAPI backend in a new window
start cmd /k "cd src\financial_news\api && python main.py"

:: Start React frontend in a new window
start cmd /k "cd frontend && npm start"

echo Services started successfully!
echo FastAPI backend running at http://localhost:8000
echo React frontend running at http://localhost:3000
