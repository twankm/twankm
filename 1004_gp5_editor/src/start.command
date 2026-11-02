#!/bin/bash
set -eu
PROJECT_ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$PROJECT_ROOT"
if [ ! -x "$PROJECT_ROOT/backend/.venv/bin/python" ]; then
    echo "Mac backend environment missing. Follow the macOS setup in README.md."
    exit 1
fi
exec "$PROJECT_ROOT/backend/.venv/bin/python" "$PROJECT_ROOT/scripts/dev.py" "$@"
