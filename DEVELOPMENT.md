# Development Guide for MCP Server Qdrant

## Quick Start with Docker Compose

The easiest way to get started with development is using Docker Compose, which is already set up with hot-reloading capabilities.

### Running with Docker Compose

```bash
# Start the MCP Server in development mode
docker-compose up

# Or to run in the background
docker-compose up -d
```

With this setup:
1. Your local code is automatically mounted into the container
2. The server automatically restarts whenever you change Python files
3. All environment variables are pre-configured
4. Port 8000 is mapped for the SSE transport

### Viewing Logs

```bash
# If running in detached mode, view logs with:
docker-compose logs -f
```

### Stopping the Server

```bash
# Stop the server
docker-compose down
```

## How It Works

### Development Setup Components

The development environment consists of three key files:

1. **`Dockerfile.dev`**: A development-specific Dockerfile that includes:
   - Python 3.12 base image
   - Watchdog for hot-reloading
   - An entrypoint script that handles installation and server startup

2. **`docker-entrypoint-dev.sh`**: An entrypoint script that:
   - Installs the project in development mode (`-e`) at startup
   - Starts the server with Watchdog monitoring for file changes

3. **`docker-compose.yml`**: Configuration that:
   - Builds from Dockerfile.dev
   - Maps port 8000
   - Mounts your local directory to `/app`
   - Sets all required environment variables

### How Hot-Reloading Works

The hot-reloading system uses Watchdog to monitor for changes to Python files. When a file changes:

1. Watchdog detects the change
2. The MCP Server process is automatically restarted
3. Your code changes take effect immediately

This eliminates the need to manually restart the container after each code change.

## Manual Docker Commands (Alternative to Docker Compose)

If you prefer not to use Docker Compose, you can use these commands:

```bash
# Build the development image
docker build -t mcp-server-qdrant-dev -f Dockerfile.dev .

# Run with hot-reloading
docker run -p 8000:8000 \
  -v $(pwd):/app \
  -e COLLECTION_NAME="code-memories" \
  -e EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2" \
  mcp-server-qdrant-dev
```

## Development Best Practices

### Working with Dependencies

If you add new dependencies to the project:

1. Add them to your `setup.py` or `pyproject.toml`
2. The container will automatically reinstall the project when restarted

### Debugging

To enable debug logs:

```bash
# Modify docker-compose.yml to add:
environment:
  - LOG_LEVEL=debug
```

### Testing Changes

The MCP Server runs on port 8000 with SSE transport in development mode. You can test it using any HTTP client:

```bash
curl http://localhost:8000/health
```

## Production vs Development

The main differences between the production `Dockerfile` and development `Dockerfile.dev` are:

1. Development installs the package in editable mode at runtime
2. Development includes hot-reloading with Watchdog
3. Development mounts your local code instead of copying it

This ensures you can quickly iterate on code changes during development while maintaining a clean production image.
