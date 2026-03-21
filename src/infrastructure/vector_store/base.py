"""Defines the abstract interface for vector storage systems.

This module provides the BaseVectorStore class, which must be implemented
by any concrete vector database client used in the RAG pipeline.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseVectorStore(ABC):
    """Abstract base class for vector database operations."""

    @abstractmethod
    def add_texts(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Adds text representations and their embeddings to the vector store.

        Args:
            texts: A list of raw text strings to be stored.
            embeddings: A list of dense vector representations.
            metadata: An optional list of dictionaries containing metadata
                (e.g., character name, response text) for each text.

        Returns:
            True if the insertion was successful, False otherwise.

        Raises:
            ValueError: If the lengths of texts and embeddings do not match.
        """
        pass

    @abstractmethod
    def search(
        self, query_embedding: List[float], top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Searches the vector store for the closest matching embeddings.

        Args:
            query_embedding: The dense vector representation of the search query.
            top_k: The number of nearest neighbors to retrieve. Defaults to 3.

        Returns:
            A list of dictionaries representing the retrieved documents. Each
            dictionary contains text, score, and associated metadata.
        """
        pass
