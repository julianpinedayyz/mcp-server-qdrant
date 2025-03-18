# MCP Server Qdrant - Technical Documentation

## Introduction

The MCP Server Qdrant is an implementation of the [Model Context Protocol (MCP)](https://modelcontextprotocol.io) that provides integration with [Qdrant](https://qdrant.tech/), a vector search engine. This server acts as a semantic memory layer, allowing large language models (LLMs) to store and retrieve information in a vector database.

## What is Model Context Protocol (MCP)?

The Model Context Protocol is an open protocol that enables seamless integration between LLM applications and external data sources and tools. It provides a standardized way to connect LLMs with the context they need, whether for AI-powered IDEs, chat interfaces, or custom AI workflows.

## Architecture Overview

The MCP Server Qdrant follows a modular architecture with the following key components:

### 1. Main Entry Point (`main.py`)

This is the entry point for the application that:
- Parses command-line arguments to determine the transport protocol (stdio or sse)
- Initializes and runs the MCP server

### 2. MCP Server Implementation (`server.py`)

The core server implementation that:
- Sets up the server lifespan context
- Configures the embedding provider and Qdrant connector
- Defines the MCP tools that clients can access
- Handles request/response flow through the MCP protocol

The server provides two main tools:
- **qdrant-store**: Stores information in the Qdrant database
- **qdrant-find**: Retrieves relevant information from the Qdrant database based on semantic search

### 3. Qdrant Connector (`qdrant.py`)

This component handles all interactions with the Qdrant vector database:
- Establishes connection to Qdrant (either remote or local)
- Creates collections automatically when needed
- Embeds documents and queries using the configured embedding provider
- Stores and retrieves information with associated metadata

### 4. Embedding System (`embeddings/`)

The embedding system is responsible for converting text into vector representations:
- **base.py**: Defines the base EmbeddingProvider interface
- **factory.py**: Creates the appropriate embedding provider based on configuration
- **fastembed.py**: Implements the FastEmbed provider (currently the only supported option)
- **types.py**: Defines embedding provider types (enum)

### 5. Configuration Management (`settings.py`)

Handles all configuration through environment variables using Pydantic:
- **QdrantSettings**: Configuration for Qdrant connection (URL, API key, collection name)
- **EmbeddingProviderSettings**: Configuration for the embedding provider
- **ToolSettings**: Configuration for tool descriptions

## How It Works

### Initialization Process

1. The server starts with a specified transport protocol (stdio or sse)
2. Environment variables are loaded into settings classes
3. The embedding provider is initialized based on configuration
4. A connection to Qdrant is established (either remote or local)
5. The MCP server is started with the defined tools

### Data Flow for Storing Information

1. Client sends a request to the "qdrant-store" tool with information and optional metadata
2. The server embeds the information using the configured embedding model
3. The embedded information is stored in Qdrant along with its metadata
4. A confirmation message is returned to the client

### Data Flow for Finding Information

1. Client sends a request to the "qdrant-find" tool with a query
2. The server embeds the query using the configured embedding model
3. Qdrant performs a vector similarity search to find relevant information
4. The most relevant results are returned to the client with the associated metadata

## Integration Options

### Tool Customization

The MCP Server Qdrant allows customization of tool descriptions to adapt to specific use cases, such as:
- Code snippet storage and retrieval
- Personal information storage
- Documentation search
- Any other text-based information storage needs

### Client Integration

This server can be used with any MCP-compatible client, including:
- Claude Desktop
- Cursor/Windsurf
- Custom MCP clients

## Usage Examples

### Storing Code Snippets

```bash
QDRANT_URL="http://localhost:6333" \
COLLECTION_NAME="code-snippets" \
TOOL_STORE_DESCRIPTION="Store reusable code snippets for later retrieval..." \
TOOL_FIND_DESCRIPTION="Search for relevant code snippets based on natural language descriptions..." \
uvx mcp-server-qdrant --transport sse
```

### Personal Memory System

```bash
QDRANT_URL="http://localhost:6333" \
COLLECTION_NAME="personal-memories" \
TOOL_STORE_DESCRIPTION="Remember this information for me..." \
TOOL_FIND_DESCRIPTION="Recall information related to..." \
uvx mcp-server-qdrant
```

## Technical Considerations

### Vector Embeddings

The server currently uses FastEmbed as the embedding provider with the default model being "sentence-transformers/all-MiniLM-L6-v2". This model produces 384-dimensional vectors that represent the semantic meaning of text.

### Collection Management

The server automatically creates a Qdrant collection if it doesn't exist, configuring it with the appropriate vector size and distance metric (COSINE).

### Transport Protocols

Two transport protocols are supported:
- **stdio**: Standard input/output transport, primarily for local MCP clients
- **sse**: Server-Sent Events transport, suitable for remote clients

## Dependencies

- **mcp**: The Model Context Protocol implementation
- **qdrant-client**: Python client for Qdrant
- **fastembed**: For generating embeddings
- **pydantic**: For settings management

## Deployment Options

The server can be deployed using:
1. Direct execution with `uvx`
2. Docker containerization
3. Integration with Smithery for automatic installation

## Conclusion

The MCP Server Qdrant provides a powerful yet simple way to add semantic memory capabilities to large language models through the Model Context Protocol. By leveraging vector search technology, it enables more contextual and relevant AI interactions across various applications.
