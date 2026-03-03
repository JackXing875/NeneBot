#!/bin/bash
# Script to run formatters and linters across the codebase.

echo "Running Ruff formatter..."
ruff format src/ scripts/

echo "Running Ruff linter..."
ruff check src/ scripts/ --fix

echo "Running Mypy static type checking..."
mypy src/

echo "Code quality checks completed!"