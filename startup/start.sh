#!/bin/bash

# Xiaoyi_QQ Framework Startup Script
# Author: ValkyrieEY

set -e

echo "Starting Xiaoyi_QQ Framework..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Resolve Python interpreter (prefer project venv)
PYTHON_BIN=""
if [ -x "$PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
elif [ -n "${RUABOT_PYTHON_CMD:-}" ] && [ -x "${RUABOT_PYTHON_CMD}" ]; then
    PYTHON_BIN="${RUABOT_PYTHON_CMD}"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
else
    echo "Python 3 not found. Please install Python 3.11+"
    exit 1
fi

PYTHON_VERSION=$("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Python version: $PYTHON_VERSION"

# Create necessary directories
mkdir -p data logs plugins

# Run the application
echo "Starting application..."
echo "Web UI: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""

"$PYTHON_BIN" -m src.main
