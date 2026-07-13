#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="python"
if [ -x "$PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
fi

"$PYTHON_BIN" -m ruff format --check src tests scripts
"$PYTHON_BIN" -m ruff check src tests scripts
"$PYTHON_BIN" -m mypy src scripts
"$PYTHON_BIN" -m pytest -q

(cd frontend && npm run build)

echo "All project checks passed."
