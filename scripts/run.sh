#!/bin/bash

set -e
set -o pipefail

echo "======================================================="
echo "        NeneBot - Runtime Service Launcher"
echo "======================================================="

echo "[0/2] Checking Ollama runtime..."

if ! command -v ollama &> /dev/null; then
    echo "[ERROR] Ollama is not installed."
    echo "Install it via: https://ollama.com"
    exit 1
fi

if ! pgrep -x "ollama" > /dev/null; then
    echo "[INFO] Ollama not running. Starting service..."
    ollama serve > /dev/null 2>&1 &
    sleep 3
    echo "[OK] Ollama service started."
else
    echo "[OK] Ollama runtime already active."
fi

cleanup() {
    echo ""
    echo "[INFO] Shutdown signal received. Terminating services..."

    if [[ -n "$BACKEND_PID" ]]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi

    if [[ -n "$FRONTEND_PID" ]]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi

    echo "[OK] Backend and frontend services stopped."
    echo "[INFO] Ollama remains running in the background."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "[1/2] Starting backend service (FastAPI on port 8000)..."

python -m src.main &
BACKEND_PID=$!

sleep 2

# Optional: health check could be added here

echo "[OK] Backend service launched (PID: $BACKEND_PID)."

echo "[2/2] Starting frontend service (Vue + Vite on port 5173)..."

cd frontend || {
    echo "[ERROR] Frontend directory not found."
    cleanup
}

npm run dev &
FRONTEND_PID=$!

echo "[OK] Frontend service launched (PID: $FRONTEND_PID)."

echo "-------------------------------------------------------"
echo "NeneBot is now running."
echo "Frontend: http://localhost:5173"
echo "Backend : http://localhost:8000"
echo "Press Ctrl+C to stop all services."
echo "-------------------------------------------------------"

wait