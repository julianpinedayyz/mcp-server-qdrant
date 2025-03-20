FROM python:3.10-slim

WORKDIR /app

# Install uv for package management
RUN pip install --no-cache-dir uv

# Install the mcp-server-qdrant package
RUN uv pip install --system --no-cache-dir mcp-server-qdrant

# Expose the default port for SSE transport
EXPOSE 8000

# Set environment variables with defaults that can be overridden at runtime
ENV QDRANT_URL="http://localhost:6333"
ENV QDRANT_API_KEY=""
ENV COLLECTION_NAME="code-memory"
ENV EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"

# Define tool descriptions for storing and finding code snippets
ENV TOOL_STORE_DESCRIPTION="Store reusable code snippets for later retrieval. \
  The 'information' parameter should contain a natural language description of what the code does, \
  while the actual code should be included in the 'metadata' parameter as a 'code' property. \
  The value of 'metadata' is a Python dictionary with strings as keys. \
  Use this whenever you generate some code snippet."

ENV TOOL_FIND_DESCRIPTION="Search for relevant code snippets based on natural language descriptions. \
  The 'query' parameter should describe what you're looking for, \
  and the tool will return the most relevant code snippets. \
  Use this when you need to find existing code snippets for reuse or reference."

# Run the server with SSE transport
CMD uvx mcp-server-qdrant --transport sse
