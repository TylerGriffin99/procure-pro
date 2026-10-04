#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

# Load .env from project root
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

cd "$BACKEND_DIR"

SUITE="${1:-all}"
shift 2>/dev/null || true

case "$SUITE" in
    unit)
        echo "Running unit tests..."
        uv run pytest tests/unit -v "$@"
        ;;
    e2e)
        echo "Running e2e tests (real LLM calls)..."
        uv run pytest tests/e2e -v -s "$@"
        ;;
    e2e-file)
        FILE="${1#backend/}"
        shift 2>/dev/null || true
        echo "Running e2e test: $FILE..."
        uv run pytest "$FILE" -v -s "$@"
        ;;
    all)
        echo "Running all tests (evals excluded)..."
        uv run pytest tests/ -v -m "not eval" "$@"
        ;;
    eval)
        echo "Running Jev matcher eval (real Jev + LLM, paid)..."
        uv run pytest tests/eval -v -s -m eval "$@"
        ;;
    *)
        echo "Usage: $0 [unit|e2e|all|eval] [pytest args...]"
        exit 1
        ;;
esac
