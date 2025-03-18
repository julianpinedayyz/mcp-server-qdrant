import logging
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, models
from qdrant_client import exceptions as qdrant_exceptions

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.exceptions import ConnectionError, CollectionError, EmbeddingError, StoreError, SearchError
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
    :param collection_name: The name of the collection to use.
    :param embedding_provider: The embedding provider to use.
    :param qdrant_local_path: The path to the storage directory for the Qdrant client, if local mode is used.
    """

    def __init__(
        self,
        qdrant_url: Optional[str],
        qdrant_api_key: Optional[str],
        collection_name: str,
        embedding_provider: EmbeddingProvider,
        qdrant_local_path: Optional[str] = None,
    ):
        self._qdrant_url = qdrant_url.rstrip("/") if qdrant_url else None
        self._qdrant_api_key = qdrant_api_key
        self._collection_name = collection_name
        self._embedding_provider = embedding_provider
        self._client = AsyncQdrantClient(
            location=qdrant_url, api_key=qdrant_api_key, path=qdrant_local_path
        )

    async def _ensure_collection_exists(self):
        """Ensure that the collection exists, creating it if necessary.
        
        Raises:
            CollectionError: If there was an error creating the collection.
            EmbeddingError: If there was an error generating embeddings.
            ConnectionError: If there was an error connecting to the Qdrant server.
        """
        with CorrelationIdFilter.correlation_id() as correlation_id:
            debug(
                logger,
                f"Checking if collection '{self._collection_name}' exists",
                {"collection_name": self._collection_name, "correlation_id": correlation_id}
            )
            
            try:
                collection_exists = await self._client.collection_exists(self._collection_name)
            except qdrant_exceptions.UnexpectedResponse as e:
                error_msg = f"Unexpected response from Qdrant server while checking collection"
                error(
                    logger,
                    error_msg,
                    {
                        "collection_name": self._collection_name, 
                        "error": str(e),
                        "correlation_id": correlation_id
                    },
                    exc_info=e
                )
                raise ConnectionError(error_msg, {"collection_name": self._collection_name}, e)
            
            if not collection_exists:
                info(
                    logger,
                    f"Collection '{self._collection_name}' does not exist, creating it",
                    {"collection_name": self._collection_name, "correlation_id": correlation_id}
                )
                
                try:
                    # Create the collection with the appropriate vector size
                    # We'll get the vector size by embedding a sample text
                    sample_vector = await self._embedding_provider.embed_query("sample text")
                    vector_size = len(sample_vector)
                except Exception as e:
                    error_msg = "Failed to generate embeddings for sample text"
                    error(
                        logger,
                        error_msg,
                        {
                            "error": str(e),
                            "correlation_id": correlation_id
                        },
                        exc_info=e
                    )
                    raise EmbeddingError(
                        error_msg,
                        {"provider": str(self._embedding_provider)},
                        e
                    )

                # Use the vector name as defined in the embedding provider
                vector_name = self._embedding_provider.get_vector_name()
                
                try:
                    await self._client.create_collection(
                        collection_name=self._collection_name,
                        vectors_config={
                            vector_name: models.VectorParams(
                                size=vector_size,
                                distance=models.Distance.COSINE,
                            )
                        },
                    )
                    info(
                        logger,
                        f"Created collection '{self._collection_name}'",
                        {
                            "collection_name": self._collection_name,
                            "vector_size": vector_size,
                            "correlation_id": correlation_id
                        }
                    )
                except Exception as e:
                    error_msg = f"Failed to create collection '{self._collection_name}'"
                    error(
                        logger,
                        error_msg,
                        {
                            "collection_name": self._collection_name,
                            "error": str(e),
                            "correlation_id": correlation_id
                        },
                        exc_info=e
                    )
                    raise CollectionError(
                        error_msg,
                        {"collection_name": self._collection_name},
                        e
                    )

    async def store(self, entry: Entry):
        """
        Store some information in the Qdrant collection, along with the specified metadata.
        
        Args:
            entry: The entry to store in the Qdrant collection.
            
        Raises:
            StoreError: If there was an error storing the entry.
            EmbeddingError: If there was an error generating embeddings.
            ConnectionError: If there was an error connecting to the Qdrant server.
            CollectionError: If there was an error creating the collection.
        """
        try:
            with CorrelationIdFilter.correlation_id() as correlation_id:
                info(
                    logger,
                    f"Storing entry in collection '{self._collection_name}'",
                    {
                        "collection_name": self._collection_name,
                        "content_length": len(entry.content),
                        "has_metadata": entry.metadata is not None,
                        "correlation_id": correlation_id
                    }
                )
                
                # Ensure collection exists first
                try:
                    await self._ensure_collection_exists()
                except (ConnectionError, CollectionError, EmbeddingError) as e:
                    # These exceptions are already properly logged, so just re-raise them
                    raise

                # Embed the document
                try:
                    embeddings = await self._embedding_provider.embed_documents([entry.content])
                except Exception as e:
                    error_msg = "Failed to generate embeddings for document"
                    error(
                        logger,
                        error_msg,
                        {
                            "content_length": len(entry.content),
                            "error": str(e),
                            "correlation_id": correlation_id
                        },
                        exc_info=e
                    )
                    raise EmbeddingError(
                        error_msg,
                        {
                            "content_length": len(entry.content),
                            "provider": str(self._embedding_provider)
                        },
                        e
                    )

                # Add to Qdrant
                vector_name = self._embedding_provider.get_vector_name()
                payload = {"document": entry.content, "metadata": entry.metadata}
                point_id = uuid.uuid4().hex
                
                try:
                    await self._client.upsert(
                        collection_name=self._collection_name,
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
                        f"Successfully stored entry in collection '{self._collection_name}'",
                        {
                            "collection_name": self._collection_name,
                            "point_id": point_id,
                            "correlation_id": correlation_id
                        }
                    )
                    
                except qdrant_exceptions.UnexpectedResponse as e:
                    error_msg = f"Unexpected response from Qdrant server while storing entry"
                    error(
                        logger,
                        error_msg,
                        {
                            "collection_name": self._collection_name, 
                            "error": str(e),
                            "correlation_id": correlation_id
                        },
                        exc_info=e
                    )
                    raise ConnectionError(error_msg, {"collection_name": self._collection_name}, e)
                except Exception as e:
                    error_msg = f"Failed to store entry in collection '{self._collection_name}'"
                    error(
                        logger,
                        error_msg,
                        {
                            "collection_name": self._collection_name,
                            "error": str(e),
                            "correlation_id": correlation_id
                        },
                        exc_info=e
                    )
                    raise StoreError(
                        error_msg,
                        {"collection_name": self._collection_name},
                        e
                    )
        except Exception as e:
            if not isinstance(e, (StoreError, EmbeddingError, ConnectionError, CollectionError)):
                error_msg = f"Error storing entry in collection '{self._collection_name}'"
                error(
                    logger,
                    error_msg,
                    {"collection_name": self._collection_name, "error": str(e)},
                    exc_info=e
                )
                raise StoreError(error_msg, {"collection_name": self._collection_name}, e)
            raise

    async def search(self, query: str, limit: int = 10) -> List[Entry]:
        """
        Find points in the Qdrant collection. If there are no entries found, an empty list is returned.
        
        Args:
            query: The query to use for the search.
            limit: Maximum number of results to return. Default is 10.
            
        Returns:
            A list of entries found.
            
        Raises:
            SearchError: If there was an error searching for entries.
            EmbeddingError: If there was an error generating embeddings.
            ConnectionError: If there was an error connecting to the Qdrant server.
        """
        try:
            with CorrelationIdFilter.correlation_id() as correlation_id:
                info(
                    logger,
                    f"Searching in collection '{self._collection_name}'",
                    {
                        "collection_name": self._collection_name,
                        "query": query,
                        "limit": limit,
                        "correlation_id": correlation_id
                    }
                )
                
                try:
                    collection_exists = await self._client.collection_exists(self._collection_name)
                    if not collection_exists:
                        warning(
                            logger,
                            f"Collection '{self._collection_name}' does not exist, returning empty results",
                            {"collection_name": self._collection_name, "correlation_id": correlation_id}
                        )
                        return []
                except qdrant_exceptions.UnexpectedResponse as e:
                    error_msg = f"Unexpected response from Qdrant server while checking collection"
                    error(
                        logger,
                        error_msg,
                        {
                            "collection_name": self._collection_name, 
                            "error": str(e),
                            "correlation_id": correlation_id
                        },
                        exc_info=e
                    )
                    raise ConnectionError(error_msg, {"collection_name": self._collection_name}, e)

                try:
                    # Embed the query
                    query_vector = await self._embedding_provider.embed_query(query)
                except Exception as e:
                    error_msg = "Failed to generate embeddings for query"
                    error(
                        logger,
                        error_msg,
                        {
                            "query": query,
                            "error": str(e),
                            "correlation_id": correlation_id
                        },
                        exc_info=e
                    )
                    raise EmbeddingError(
                        error_msg,
                        {
                            "query": query,
                            "provider": str(self._embedding_provider)
                        },
                        e
                    )

                vector_name = self._embedding_provider.get_vector_name()

                try:
                    # Search in Qdrant
                    search_results = await self._client.search(
                        collection_name=self._collection_name,
                        query_vector=models.NamedVector(name=vector_name, vector=query_vector),
                        limit=limit,
                    )
                except qdrant_exceptions.UnexpectedResponse as e:
                    error_msg = f"Unexpected response from Qdrant server while searching"
                    error(
                        logger,
                        error_msg,
                        {
                            "collection_name": self._collection_name, 
                            "error": str(e),
                            "correlation_id": correlation_id
                        },
                        exc_info=e
                    )
                    raise ConnectionError(error_msg, {"collection_name": self._collection_name}, e)
                except Exception as e:
                    error_msg = f"Failed to search in collection '{self._collection_name}'"
                    error(
                        logger,
                        error_msg,
                        {
                            "collection_name": self._collection_name,
                            "query": query,
                            "error": str(e),
                            "correlation_id": correlation_id
                        },
                        exc_info=e
                    )
                    raise SearchError(error_msg, {"collection_name": self._collection_name, "query": query}, e)

                results = [
                    Entry(
                        content=result.payload["document"],
                        metadata=result.payload.get("metadata"),
                    )
                    for result in search_results
                ]
                
                debug(
                    logger,
                    f"Found {len(results)} results for query in collection '{self._collection_name}'",
                    {
                        "collection_name": self._collection_name,
                        "query": query,
                        "result_count": len(results),
                        "correlation_id": correlation_id
                    }
                )
                
                return results
        except Exception as e:
            if not isinstance(e, (SearchError, EmbeddingError, ConnectionError)):
                error_msg = f"Error searching in collection '{self._collection_name}'"
                error(
                    logger,
                    error_msg,
                    {"collection_name": self._collection_name, "query": query, "error": str(e)},
                    exc_info=e
                )
                raise SearchError(error_msg, {"collection_name": self._collection_name, "query": query}, e)
            raise
