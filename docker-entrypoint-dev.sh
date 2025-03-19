#!/bin/bash
set -e

# Install the project in development mode
echo "Installing mcp-server-qdrant in development mode..."
uv pip install --system -e .

# Start the server with hot-reload
echo "Starting MCP Server with hot-reload..."
watchmedo auto-restart \
  --directory=/app \
  --pattern="*.py" \
  --recursive \
  -- python -m mcp_server_qdrant.main --transport sse --log-level debug
