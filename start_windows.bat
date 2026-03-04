@echo off
:: Set console to UTF-8 encoding to prevent character issues
chcp 65001 >nul
title NeneBot - One-Click Startup
color 0D

echo =======================================================
echo.
echo                 NeneBot Startup Utility
echo.
echo        Initializing environment and services...
echo.
echo =======================================================
echo.

:: 1. System Environment Check
echo [1/5] Checking system prerequisites...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    echo Please install Python 3.10 or later from:
    echo https://www.python.org/
    echo Make sure to enable "Add Python to PATH" during installation.
    pause
    exit /b
)

npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed.
    echo Please download and install the LTS version from:
    echo https://nodejs.org/
    pause
    exit /b
)

echo System prerequisites verified.

:: 2. Backend Setup
echo [2/5] Configuring backend environment...

if not exist "venv" (
    echo    - Creating Python virtual environment...
    python -m venv venv
)

call venv\Scripts\activate
echo    - Installing/updating backend dependencies...
pip install -r requirements.txt -q

echo Backend environment ready.

:: 3. Frontend Setup
echo [3/5] Configuring frontend environment...

cd frontend
if not exist "node_modules" (
    echo    - Installing frontend dependencies...
    call npm install --silent
)
cd ..

echo Frontend environment ready.

:: 4. Start Ollama Engine
echo [4/5] Starting local LLM engine (Ollama)...

:: Attempt to start Ollama silently (ignored if already running)
start /B ollama serve >nul 2>&1

echo Ollama engine initialized.

:: 5. Launch Services
echo [5/5] Launching backend and frontend services...
echo.

:: Start backend service in a new terminal window
start "NeneBot Backend Service" cmd /c "venv\Scripts\activate && python -m src.main"

:: Start frontend service in a new terminal window
start "NeneBot Frontend Service" cmd /c "cd frontend && npm run dev"

:: Wait 3 seconds before opening browser
echo Waiting for services to initialize...
timeout /t 3 /nobreak >nul

start http://localhost:5173

echo.
echo =======================================================
echo Startup completed successfully.
echo If the browser does not open automatically, visit:
echo http://localhost:5173
echo.
echo To stop the application, close the backend and frontend
echo terminal windows.
echo =======================================================
pause