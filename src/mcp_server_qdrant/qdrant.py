import logging
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http import exceptions as qdrant_exceptions

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.exceptions import ConfigurationError, ConnectionError, CollectionError, EmbeddingError, StoreError, SearchError
from mcp_server_qdrant.logging import debug, info, warning, error, critical, CorrelationIdFilter

logger = logging.getLogger(__name__)

Metadata = Dict[str, Any]


class Entry(BaseModel):
    """
    A single entry in the Qdrant collection.
    """

    content: str
    metadata: Optional[Metadata] = None


class QdrantConnector:
    """
    Encapsulates the connection to a Qdrant server and all the methods to interact with it.
    :param qdrant_url: The URL of the Qdrant server.
    :param qdrant_api_key: The API key to use for the Qdrant server.
    :param collection_name: The name of the default collection to use. If not provided, each tool will require
                            the collection name to be provided.
    :param embedding_provider: The embedding provider to use.
    :param qdrant_local_path: The path to the storage directory for the Qdrant client, if local mode is used.
    """

    def __init__(
        self,
        qdrant_url: Optional[str],
        qdrant_api_key: Optional[str],
        collection_name: Optional[str],
        embedding_provider: EmbeddingProvider,
        qdrant_local_path: Optional[str] = None,
    ):
        self._qdrant_url = qdrant_url.rstrip("/") if qdrant_url else None
        self._qdrant_api_key = qdrant_api_key
        self._default_collection_name = collection_name
        self._embedding_provider = embedding_provider
        self._client = AsyncQdrantClient(
            location=qdrant_url, api_key=qdrant_api_key, path=qdrant_local_path
        )

    async def get_collection_names(self) -> list[str]:
        """
        Get the names of all collections in the Qdrant server.
        :return: A list of collection names.
        """
        with CorrelationIdFilter.correlation_id() as correlation_id:
            context = {"correlation_id": correlation_id}
            info(logger, "Fetching collection names", context)
            try:
                response = await self._client.get_collections()
                names = [collection.name for collection in response.collections]
                debug(logger, f"Found {len(names)} collections", {**context, "count": len(names)})
                return names
            except qdrant_exceptions.UnexpectedResponse as e:
                error_msg = "Unexpected response from Qdrant server while fetching collections"
                error(logger, error_msg, {**context, "error": str(e)}, exc_info=e)
                raise ConnectionError(error_msg, {}, e)
            except Exception as e:
                error_msg = "Failed to fetch collection names"
                error(logger, error_msg, {**context, "error": str(e)}, exc_info=e)
                # Use a generic ConnectionError, or define a more specific one if needed
                raise ConnectionError(error_msg, {}, e)

    async def _ensure_collection_exists(self, collection_name_to_ensure: str):
        """Ensure that the collection exists, creating it if necessary.

        Args:
            collection_name_to_ensure: The name of the collection to check/create.

        Raises:
            CollectionError: If there was an error creating the collection.
            EmbeddingError: If there was an error generating embeddings.
            ConnectionError: If there was an error connecting to the Qdrant server.
        """
        with CorrelationIdFilter.correlation_id() as correlation_id:
            context = {"collection_name": collection_name_to_ensure, "correlation_id": correlation_id}
            debug(
                logger,
                f"Checking if collection '{collection_name_to_ensure}' exists",
                context
            )

            try:
                collection_exists = await self._client.collection_exists(collection_name_to_ensure)
            except qdrant_exceptions.UnexpectedResponse as e:
                error_msg = f"Unexpected response from Qdrant server while checking collection '{collection_name_to_ensure}'"
                error(logger, error_msg, {**context, "error": str(e)}, exc_info=e)
                raise ConnectionError(error_msg, {"collection_name": collection_name_to_ensure}, e)

            if not collection_exists:
                info(
                    logger,
                    f"Collection '{collection_name_to_ensure}' does not exist, creating it",
                    context
                )

                try:
                    # Create the collection with the appropriate vector size
                    # We'll get the vector size by embedding a sample text
                    sample_vector = await self._embedding_provider.embed_query("sample text")
                    vector_size = len(sample_vector)
                except Exception as e:
                    error_msg = "Failed to generate embeddings for sample text to determine vector size"
                    # Use a broader context here as collection name isn't directly relevant yet
                    error_ctx = {"error": str(e), "correlation_id": correlation_id}
                    error(logger, error_msg, error_ctx, exc_info=e)
                    raise EmbeddingError(error_msg, {"provider": str(self._embedding_provider)}, e)

                # Use the vector name as defined in the embedding provider
                vector_name = self._embedding_provider.get_vector_name()

                try:
                    await self._client.create_collection(
                        collection_name=collection_name_to_ensure,
                        vectors_config={
                            vector_name: models.VectorParams(
                                size=vector_size,
                                distance=models.Distance.COSINE,
                            )
                        },
                    )
                    info(
                        logger,
                        f"Created collection '{collection_name_to_ensure}'",
                        {**context, "vector_size": vector_size}
                    )
                except Exception as e:
                    error_msg = f"Failed to create collection '{collection_name_to_ensure}'"
                    error(logger, error_msg, {**context, "error": str(e)}, exc_info=e)
                    raise CollectionError(error_msg, {"collection_name": collection_name_to_ensure}, e)

    async def store(self, entry: Entry, *, collection_name: Optional[str] = None):
        """
        Store some information in the Qdrant collection, along with the specified metadata.

        Args:
            entry: The entry to store in the Qdrant collection.
            collection_name: The name of the collection to store the information in, optional.
                             If not provided, the default collection is used.

        Raises:
            ConfigurationError: If no collection name is specified and no default is configured.
            StoreError: If there was an error storing the entry.
            EmbeddingError: If there was an error generating embeddings.
            ConnectionError: If there was an error connecting to the Qdrant server.
            CollectionError: If there was an error creating the collection.
        """
        target_collection_name = collection_name or self._default_collection_name
        if not target_collection_name:
            # Handle error: No collection name specified and no default set
            raise ConfigurationError("Qdrant Store Error: No collection name specified and no default configured.", {})

        try:
            with CorrelationIdFilter.correlation_id() as correlation_id:
                context = {
                    "collection_name": target_collection_name,
                    "content_length": len(entry.content),
                    "has_metadata": entry.metadata is not None,
                    "correlation_id": correlation_id
                }
                info(
                    logger,
                    f"Storing entry in collection '{target_collection_name}'",
                    context
                )

                # Ensure collection exists first
                try:
                    await self._ensure_collection_exists(target_collection_name)
                except (ConnectionError, CollectionError, EmbeddingError) as e:
                    # These exceptions are already properly logged in _ensure_collection_exists, so just re-raise
                    raise

                # Embed the document
                try:
                    embeddings = await self._embedding_provider.embed_documents([entry.content])
                except Exception as e:
                    error_msg = "Failed to generate embeddings for document"
                    error_ctx = {
                        "collection_name": target_collection_name, # Add collection name to context
                        "content_length": len(entry.content),
                        "error": str(e),
                        "correlation_id": correlation_id
                    }
                    error(logger, error_msg, error_ctx, exc_info=e)
                    raise EmbeddingError(error_msg, {**error_ctx, "provider": str(self._embedding_provider)}, e)

                # Add to Qdrant
                vector_name = self._embedding_provider.get_vector_name()
                payload = {"document": entry.content, "metadata": entry.metadata}
                point_id = uuid.uuid4().hex

                try:
                    await self._client.upsert(
                        collection_name=target_collection_name, # Use target name
                        points=[
                            models.PointStruct(
                                id=point_id,
                                vector={vector_name: embeddings[0]},
                                payload=payload,
                            )
                        ],
                    )

                    debug(
                        logger,
                        f"Successfully stored entry in collection '{target_collection_name}'",
                        {**context, "point_id": point_id}
                    )

                except qdrant_exceptions.UnexpectedResponse as e:
                    error_msg = f"Unexpected response from Qdrant server while storing entry in '{target_collection_name}'"
                    error(logger, error_msg, {**context, "error": str(e)}, exc_info=e)
                    raise ConnectionError(error_msg, {"collection_name": target_collection_name}, e)
                except Exception as e:
                    error_msg = f"Failed to store entry in collection '{target_collection_name}'"
                    error(logger, error_msg, {**context, "error": str(e)}, exc_info=e)
                    raise StoreError(error_msg, {"collection_name": target_collection_name}, e)
        except Exception as e:
            # Catch exceptions not already handled (like ConfigurationError) or re-raised custom ones
            if not isinstance(e, (ConfigurationError, StoreError, EmbeddingError, ConnectionError, CollectionError)):
                error_msg = f"Unexpected error storing entry in collection '{target_collection_name or 'UNKNOWN'}'"
                error_ctx = {"collection_name": target_collection_name or 'UNKNOWN', "error": str(e)}
                # Attempt to get correlation_id if possible, otherwise omit
                try:
                    error_ctx["correlation_id"] = correlation_id
                except NameError:
                    pass
                error(logger, error_msg, error_ctx, exc_info=e)
                raise StoreError(error_msg, {"collection_name": target_collection_name or 'UNKNOWN'}, e)
            raise # Re-raise known custom exceptions

    async def search(self, query: str, *, collection_name: Optional[str] = None, limit: int = 10) -> List[Entry]:
        """
        Find points in the Qdrant collection. If there are no entries found, an empty list is returned.

        Args:
            query: The query to use for the search.
            collection_name: The name of the collection to search in, optional. If not provided,
                             the default collection is used.
            limit: Maximum number of results to return. Default is 10.

        Returns:
            A list of entries found.

        Raises:
            ConfigurationError: If no collection name is specified and no default is configured.
            SearchError: If there was an error searching for entries.
            EmbeddingError: If there was an error generating embeddings.
            ConnectionError: If there was an error connecting to the Qdrant server.
        """
        target_collection_name = collection_name or self._default_collection_name
        if not target_collection_name:
            # Handle error: No collection name specified and no default set
            raise ConfigurationError("Qdrant Search Error: No collection name specified and no default configured.", {})

        try:
            with CorrelationIdFilter.correlation_id() as correlation_id:
                context = {
                    "collection_name": target_collection_name,
                    "query": query,
                    "limit": limit,
                    "correlation_id": correlation_id
                }
                info(
                    logger,
                    f"Searching in collection '{target_collection_name}'",
                    context
                )

                try:
                    collection_exists = await self._client.collection_exists(target_collection_name) # Use target name
                    if not collection_exists:
                        warning(
                            logger,
                            f"Collection '{target_collection_name}' does not exist for search, returning empty results",
                            context
                        )
                        return []
                except qdrant_exceptions.UnexpectedResponse as e:
                    error_msg = f"Unexpected response from Qdrant server while checking collection '{target_collection_name}' for search"
                    error(logger, error_msg, {**context, "error": str(e)}, exc_info=e)
                    raise ConnectionError(error_msg, {"collection_name": target_collection_name}, e)

                try:
                    # Embed the query
                    query_vector = await self._embedding_provider.embed_query(query)
                except Exception as e:
                    error_msg = "Failed to generate embeddings for query"
                    error_ctx = {
                        "collection_name": target_collection_name, # Add collection name
                        "query": query,
                        "error": str(e),
                        "correlation_id": correlation_id
                    }
                    error(logger, error_msg, error_ctx, exc_info=e)
                    raise EmbeddingError(error_msg, {**error_ctx, "provider": str(self._embedding_provider)}, e)

                vector_name = self._embedding_provider.get_vector_name()

                try:
                    # Search in Qdrant
                    # Use client.search (from user's version) instead of client.query_points (from HEAD)
                    search_results = await self._client.search(
                        collection_name=target_collection_name, # Use target name
                        query_vector=models.NamedVector(name=vector_name, vector=query_vector), # Use NamedVector for client.search
                        limit=limit,
                    )
                except qdrant_exceptions.UnexpectedResponse as e:
                    error_msg = f"Unexpected response from Qdrant server while searching in '{target_collection_name}'"
                    error(logger, error_msg, {**context, "error": str(e)}, exc_info=e)
                    raise ConnectionError(error_msg, {"collection_name": target_collection_name}, e)
                except Exception as e:
                    error_msg = f"Failed to search in collection '{target_collection_name}'"
                    error(logger, error_msg, {**context, "error": str(e)}, exc_info=e)
                    raise SearchError(error_msg, {"collection_name": target_collection_name, "query": query}, e)

                # Adapt result parsing for client.search which returns ScoredPoint directly
                results = [
                    Entry(
                        content=result.payload["document"],
                        metadata=result.payload.get("metadata"),
                    )
                    for result in search_results # Iterate directly over search_results
                ]

                debug(
                    logger,
                    f"Found {len(results)} results for query in collection '{target_collection_name}'",
                    {**context, "result_count": len(results)}
                )

                return results
        except Exception as e:
            # Catch exceptions not already handled (like ConfigurationError) or re-raised custom ones
            if not isinstance(e, (ConfigurationError, SearchError, EmbeddingError, ConnectionError)):
                error_msg = f"Unexpected error searching in collection '{target_collection_name or 'UNKNOWN'}'"
                error_ctx = {"collection_name": target_collection_name or 'UNKNOWN', "query": query, "error": str(e)}
                # Attempt to get correlation_id if possible, otherwise omit
                try:
                    error_ctx["correlation_id"] = correlation_id
                except NameError:
                    pass
                error(logger, error_msg, error_ctx, exc_info=e)
                raise SearchError(error_msg, {"collection_name": target_collection_name or 'UNKNOWN', "query": query}, e)
            raise # Re-raise known custom exceptions
