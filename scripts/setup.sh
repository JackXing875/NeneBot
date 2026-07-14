#!/bin/bash

echo "======================================================="
echo "       Persona Studio - Linux Environment Setup"
echo "======================================================="
echo ""

echo "[1/5] Verifying system prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 is not installed."
    echo "Install it using: sudo apt update && sudo apt install python3 python3-venv"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "[ERROR] Node.js and npm are not installed."
    echo "Recommended: install via nvm, or run: sudo apt install nodejs npm"
    exit 1
fi

echo "[OK] Python3 and Node.js environment verified."

# Load .env to check LLM_PROVIDER (default to ollama if not set)
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

LLM_PROVIDER="${LLM_PROVIDER:-ollama}"

if [ "$LLM_PROVIDER" = "ollama" ]; then
    echo "[2/5] Checking local LLM runtime (Ollama)..."

    if ! command -v ollama &> /dev/null; then
        echo "[INFO] Ollama not detected. Installing runtime..."
        curl -fsSL https://ollama.com/install.sh | sh
    else
        echo "[OK] Ollama runtime detected."
    fi

    echo "[3/5] Starting Ollama service and pulling Qwen2.5 model..."

    if ! pgrep -x "ollama" > /dev/null; then
        echo "[INFO] Launching Ollama service..."
        ollama serve > /dev/null 2>&1 &
        sleep 3
    fi

    ollama pull qwen2.5
    echo "[OK] Model installation completed."
else
    echo "[2/5] Skipping Ollama setup (LLM_PROVIDER=${LLM_PROVIDER})."
    echo "[3/5] Skipping model pull (LLM_PROVIDER=${LLM_PROVIDER})."
fi

echo "[4/5] Setting up backend RAG engine..."

if [ ! -d "venv" ]; then
    echo "[INFO] Creating Python virtual environment..."
    python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "[INFO] Installing backend dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -e . --no-deps -q

echo "[OK] Backend dependencies installed."

echo "[5/5] Setting up frontend interface..."

cd frontend || exit 1
npm ci --silent
cd ..

echo "[OK] Frontend dependencies installed."

echo "[INFO] Building the original demo Character Pack artifact..."
persona pack validate packs/demo
persona pack build packs/demo
persona pack promote mira-demo 1.0.0

echo ""
echo "======================================================="
echo "Setup completed successfully."
echo ""
echo "To start the application, run:"
echo "   ./scripts/run.sh"
echo "======================================================="
