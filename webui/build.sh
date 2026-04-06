#!/bin/bash
# Build script for webui

echo " Building Next.js WebUI..."

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo " Installing dependencies..."
    npm install
fi

# Build the project
echo "  Building production bundle..."
npm run build

echo " Build complete! Output: ../src/ui/static"

