@echo off
rem trandeer local run: build data.json, then serve web/ and the AI helper (/api/chat) at http://127.0.0.1:8000 . Close this window (or Ctrl+C) to stop.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [error] .venv not found. Set up the virtual environment first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" build.py
if errorlevel 1 echo [warn] build failed. Showing the previous data.json if it exists.
start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" serve.py
pause
