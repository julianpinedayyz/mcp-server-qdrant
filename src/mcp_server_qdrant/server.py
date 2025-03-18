import json
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional

from mcp.server import Server
from mcp.server.fastmcp import Context, FastMCP

from mcp_server_qdrant.embeddings.factory import create_embedding_provider
from mcp_server_qdrant.exceptions import ConfigurationError, ConnectionError, EmbeddingError, SearchError, StoreError
from mcp_server_qdrant.logging import configure_logging, debug, info, warning, error, critical, CorrelationIdFilter
from mcp_server_qdrant.qdrant import Entry, Metadata, QdrantConnector
from mcp_server_qdrant.settings import (
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)

logger = logging.getLogger(__name__)

# Configure logging when this module is imported
configure_logging(level=logging.INFO, json_format=True, include_correlation_id=True)


@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[Dict]:  # noqa
    """
    Context manager to handle the lifespan of the server.
    This is used to configure the embedding provider and Qdrant connector.
    All the configuration is now loaded from the environment variables.
    Settings handle that for us.
    """
    with CorrelationIdFilter.correlation_id() as correlation_id:
        context_data = {"correlation_id": correlation_id}
        info(logger, "Starting MCP server lifespan", context_data)

        try:
            # Load embedding provider settings
            try:
                embedding_provider_settings = EmbeddingProviderSettings()
                context_data.update({
                    "embedding_provider": str(embedding_provider_settings.provider_type),
                    "embedding_model": embedding_provider_settings.model_name
                })
            except Exception as e:
                error_msg = "Failed to load embedding provider settings"
                error(logger, error_msg, context_data, exc_info=e)
                raise ConfigurationError(error_msg, context_data, e)

            # Create embedding provider
            try:
                embedding_provider = create_embedding_provider(embedding_provider_settings)
                info(
                    logger,
                    "Using embedding provider",
                    {
                        "provider": str(embedding_provider_settings.provider_type),
                        "model": embedding_provider_settings.model_name,
                        "correlation_id": correlation_id
                    }
                )
            except Exception as e:
                error_msg = "Failed to create embedding provider"
                error(logger, error_msg, context_data, exc_info=e)
                raise EmbeddingError(
                    error_msg,
                    {
                        "provider": str(embedding_provider_settings.provider_type),
                        "model": embedding_provider_settings.model_name
                    },
                    e
                )

            # Load Qdrant settings
            try:
                qdrant_configuration = QdrantSettings()
                location_info = qdrant_configuration.get_qdrant_location()
                context_data.update({
                    "qdrant_location": location_info,
                    "collection_name": qdrant_configuration.collection_name
                })
            except Exception as e:
                error_msg = "Failed to load Qdrant settings"
                error(logger, error_msg, context_data, exc_info=e)
                raise ConfigurationError(error_msg, context_data, e)

            # Create Qdrant connector
            try:
                qdrant_connector = QdrantConnector(
                    qdrant_configuration.location,
                    qdrant_configuration.api_key,
                    qdrant_configuration.collection_name,
                    embedding_provider,
                    qdrant_configuration.local_path,
                )
                info(
                    logger,
                    "Connected to Qdrant",
                    {
                        "location": location_info,
                        "collection_name": qdrant_configuration.collection_name,
                        "correlation_id": correlation_id
                    }
                )
            except Exception as e:
                error_msg = "Failed to connect to Qdrant"
                error(logger, error_msg, context_data, exc_info=e)
                raise ConnectionError(
                    error_msg,
                    {
                        "location": location_info,
                        "collection_name": qdrant_configuration.collection_name
                    },
                    e
                )

            info(logger, "MCP server ready", context_data)
            yield {
                "embedding_provider": embedding_provider,
                "qdrant_connector": qdrant_connector,
                "correlation_id": correlation_id,
            }
        except Exception as e:
            error(logger, f"Error during server lifespan: {str(e)}", context_data, exc_info=e)
            # Re-raise the exception to ensure FastMCP knows there was a problem
            raise
        finally:
            info(logger, "MCP server lifespan ending", context_data)


# FastMCP is an alternative interface for declaring the capabilities
# of the server. Its API is based on FastAPI.
mcp = FastMCP("mcp-server-qdrant", lifespan=server_lifespan)

# Load the tool settings from the env variables, if they are set,
# or use the default values otherwise.
tool_settings = ToolSettings()


@mcp.tool(name="qdrant-store", description=tool_settings.tool_store_description)
async def store(
    ctx: Context,
    information: str,
    # The `metadata` parameter is defined as non-optional, but it can be None.
    # If we set it to be optional, some of the MCP clients, like Cursor, cannot
    # handle the optional parameter correctly.
    metadata: Metadata = None,
) -> str:
    """
    Store some information in Qdrant.

    Args:
        ctx: The context for the request.
        information: The information to store.
        metadata: JSON metadata to store with the information, optional.

    Returns:
        A message indicating that the information was stored.

    Raises:
        StoreError: If there was an error storing the information.
        EmbeddingError: If there was an error generating embeddings.
        ConnectionError: If there was an error connecting to the Qdrant server.
    """
    # Get the correlation ID from the lifespan context or generate a new one
    correlation_id = ctx.request_context.lifespan_context.get("correlation_id")
    with CorrelationIdFilter.correlation_id(correlation_id) as used_correlation_id:
        context_data = {
            "correlation_id": used_correlation_id,
            "information_length": len(information),
            "has_metadata": metadata is not None,
        }

        info(logger, "Received store request", context_data)
        await ctx.debug(f"Storing information in Qdrant (length: {len(information)})")

        try:
            qdrant_connector: QdrantConnector = ctx.request_context.lifespan_context[
                "qdrant_connector"
            ]
            entry = Entry(content=information, metadata=metadata)

            debug(
                logger,
                "Storing entry in Qdrant",
                {**context_data, "metadata_keys": list(metadata.keys()) if metadata else None}
            )

            try:
                await qdrant_connector.store(entry)
                info(logger, "Successfully stored information in Qdrant", context_data)
                return f"Remembered: {information}"
            except (StoreError, EmbeddingError, ConnectionError) as e:
                # Log the error and provide a user-friendly message
                error(logger, f"Failed to store information: {str(e)}", context_data, exc_info=e)
                error_message = f"Failed to store information: {e.message}"

                # Send error details to client debug channel
                await ctx.debug(f"Error: {error_message}")

                # Re-raise the exception for proper error handling
                raise
        except Exception as e:
            error_msg = "Unexpected error during store operation"
            error(logger, error_msg, context_data, exc_info=e)
            await ctx.debug(f"Error: {str(e)}")

            if not isinstance(e, (StoreError, EmbeddingError, ConnectionError)):
                raise StoreError(error_msg, context_data, e)
            raise


@mcp.tool(name="qdrant-find", description=tool_settings.tool_find_description)
async def find(ctx: Context, query: str, limit: int = 10) -> List[str]:
    """
    Find memories in Qdrant.

    Args:
        ctx: The context for the request.
        query: The query to use for the search.
        limit: Maximum number of results to return. Default is 10.

    Returns:
        A list of entries found formatted as strings.

    Raises:
        SearchError: If there was an error searching for entries.
        EmbeddingError: If there was an error generating embeddings.
        ConnectionError: If there was an error connecting to the Qdrant server.
    """
    # Get the correlation ID from the lifespan context or generate a new one
    correlation_id = ctx.request_context.lifespan_context.get("correlation_id")
    with CorrelationIdFilter.correlation_id(correlation_id) as used_correlation_id:
        context_data = {
            "correlation_id": used_correlation_id,
            "query": query,
            "limit": limit,
        }

        info(logger, "Received find request", context_data)
        await ctx.debug(f"Finding results for query: {query} (limit: {limit})")

        try:
            qdrant_connector: QdrantConnector = ctx.request_context.lifespan_context[
                "qdrant_connector"
            ]

            try:
                entries = await qdrant_connector.search(query, limit)

                info(
                    logger,
                    f"Found {len(entries)} results for query",
                    {**context_data, "result_count": len(entries)}
                )

                if not entries:
                    no_results_message = f"No information found for the query '{query}'"
                    debug(logger, no_results_message, context_data)
                    return [no_results_message]

                content = [
                    f"Results for the query '{query}'",
                ]

                for i, entry in enumerate(entries):
                    # Format the metadata as a JSON string and produce XML-like output
                    entry_metadata = json.dumps(entry.metadata) if entry.metadata else ""
                    content.append(
                        f"<entry><content>{entry.content}</content><metadata>{entry_metadata}</metadata></entry>"
                    )
                    debug(
                        logger,
                        f"Result {i+1}/{len(entries)}",
                        {
                            **context_data,
                            "content_length": len(entry.content),
                            "has_metadata": entry.metadata is not None
                        }
                    )

                return content

            except (SearchError, EmbeddingError, ConnectionError) as e:
                # Log the error and provide a user-friendly message
                error(logger, f"Failed to search for information: {str(e)}", context_data, exc_info=e)
                error_message = f"Failed to search for information: {e.message}"

                # Send error details to client debug channel
                await ctx.debug(f"Error: {error_message}")

                # Re-raise the exception for proper error handling
                raise
        except Exception as e:
            error_msg = "Unexpected error during find operation"
            error(logger, error_msg, context_data, exc_info=e)
            await ctx.debug(f"Error: {str(e)}")

            if not isinstance(e, (SearchError, EmbeddingError, ConnectionError)):
                raise SearchError(error_msg, context_data, e)
            raise
