#!/bin/bash

set -e
set -o pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="python"
if [ -x "$PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
fi

exec "$PYTHON_BIN" scripts/launch.py dev "$@"
