#!/bin/bash

# Xiaoyi_QQ Framework Startup Script
# Author: ValkyrieEY

set -e

echo "Starting Xiaoyi_QQ Framework..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Python 3 not found. Please install Python 3.11+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Python version: $PYTHON_VERSION"

# Create necessary directories
mkdir -p data logs plugins

# Run the application
echo "Starting application..."
echo "Web UI: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""

python3 -m src.main

