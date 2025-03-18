"""
Custom exceptions for the MCP Server Qdrant.
"""
from typing import Any, Dict, Optional


class MCPServerQdrantError(Exception):
    """Base exception for all MCP Server Qdrant errors."""

    def __init__(
        self, 
        message: str, 
        details: Optional[Dict[str, Any]] = None, 
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.details = details or {}
        self.original_error = original_error
        super().__init__(message)


class ConfigurationError(MCPServerQdrantError):
    """Raised when there is an error in the configuration."""
    pass


class ConnectionError(MCPServerQdrantError):
    """Raised when there is an error connecting to the Qdrant server."""
    pass


class EmbeddingError(MCPServerQdrantError):
    """Raised when there is an error generating embeddings."""
    pass


class CollectionError(MCPServerQdrantError):
    """Raised when there is an error managing collections."""
    pass


class StoreError(MCPServerQdrantError):
    """Raised when there is an error storing data."""
    pass


class SearchError(MCPServerQdrantError):
    """Raised when there is an error searching for data."""
    pass
