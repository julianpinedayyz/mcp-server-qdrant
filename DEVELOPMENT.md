# Development Guide for MCP Server Qdrant

## Running with Docker for Development

When developing, it's useful to mount your local code directory into the Docker container. This allows you to make changes locally and have them immediately available in the container without rebuilding the image.

### Building the Development Image

First, build a development version of the image:

```bash
docker build -t mcp-server-qdrant-dev .
```

### Running with Volume Mount

To run the container with your local code mounted:

```bash
docker run -p 8000:8000 \
  -v /Users/julianpineda/Sandbox/MCPs/mcp-server-qdrant:/app \
  -e COLLECTION_NAME="code-memories" \
  -e EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2" \
  mcp-server-qdrant-dev
```

This command:
1. Maps port 8000 from the container to your local machine
2. Mounts your local project directory to `/app` in the container
3. Sets the required environment variables
4. Uses the development image you built

### Hot Reload vs. Restart

#### About File Syncing

The volume mount (`-v`) ensures that your local files are synced with the container. Any changes you make to files on your local machine will be immediately visible in the container.

#### Server Restart Requirements

However, **the Python process won't automatically detect changes**. You'll need to restart the container when you:

- Modify Python code
- Change configuration files
- Update dependencies

To implement hot-reload functionality, you could:

1. Install development tools like `watchdog` or `nodemon` in the container
2. Modify the Dockerfile to use these tools during development
3. Create a development-specific entrypoint script

## Development Dockerfile

For a better development experience, you can create a `Dockerfile.dev` with hot-reload capabilities:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv for package management
RUN pip install --no-cache-dir uv watchdog[watchmedo]

# Install the project in development mode
COPY . .
RUN uv pip install --system -e .

# Expose the default port for SSE transport
EXPOSE 8000

# Development command with hot reload
CMD watchmedo auto-restart --directory=/app --pattern="*.py" --recursive -- python -m mcp_server_qdrant.main --transport sse
```

This development Dockerfile adds:
- Installation of `watchdog` for file monitoring
- Installation of the project in editable mode (`-e`)
- A command that restarts the server when Python files change

You would run this with the same volume mount as before:

```bash
docker build -t mcp-server-qdrant-dev -f Dockerfile.dev .
docker run -p 8000:8000 -v /Users/julianpineda/Sandbox/MCPs/mcp-server-qdrant:/app mcp-server-qdrant-dev
```

## Alternative: Using docker-compose

For an even better development experience, you can use `docker-compose`:

```yaml
# docker-compose.yml
version: '3'
services:
  mcp-server:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    environment:
      - COLLECTION_NAME=code-memories
      - EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Then run with:

```bash
docker-compose up
```

This will provide the same hot-reload functionality with a simpler command.
