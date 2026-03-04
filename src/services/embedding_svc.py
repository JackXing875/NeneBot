"""Service module for generating dense vector embeddings from text.

This module wraps the sentence-transformers library to provide a clean,
reusable interface for text vectorization within the RAG pipeline.
"""

import logging
from typing import List

import torch
from sentence_transformers import SentenceTransformer

from src.core.config import settings

# Configure basic logging for the service
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service class for generating text embeddings using SentenceTransformers.

    Attributes:
        model: The loaded SentenceTransformer model instance.
        device: The computing device (CPU or CUDA) used for inference.
    """

    def __init__(self) -> None:
        """Initializes the EmbeddingService and loads the model into memory."""
        # Automatically detect if a GPU is available, fallback to CPU for WSL/local
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading embedding model: {settings.embedding_model_name}")
        logger.info(f"Using device: {self.device}")

        # Load the model specified in the global settings
        self.model = SentenceTransformer(settings.embedding_model_name, device=self.device)

    def encode(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Encodes a list of strings into dense vector representations.

        Args:
            texts: A list of raw text strings to be vectorized.
            batch_size: The number of texts to process simultaneously. Defaults to 32.

        Returns:
            A list of lists containing floats, where each inner list is the
            embedding vector corresponding to the input text.
        """
        if not texts:
            return []

        # Convert texts to embeddings using the underlying model
        # convert_to_numpy=True ensures compatibility with FAISS
        embeddings = self.model.encode(
            texts, batch_size=batch_size, convert_to_numpy=True, show_progress_bar=False
        )

        # Convert numpy arrays to nested Python lists for the generic interface
        return embeddings.tolist()
