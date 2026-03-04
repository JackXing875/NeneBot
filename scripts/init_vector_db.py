"""Data ingestion script to initialize the vector database.

This script reads the raw conversational data from a JSONL file, extracts
the user queries and bot responses, generates embeddings for the queries,
and stores them in the FAISS vector database alongside their metadata.
"""

import json
import logging
import os
from typing import Any, Dict, List

from tqdm import tqdm

from src.core.config import settings
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.services.embedding_svc import EmbeddingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_jsonl_data(file_path: str) -> List[Dict[str, Any]]:
    """Loads and parses a standard JSONL dataset file.

    Args:
        file_path: The absolute or relative path to the JSONL file.

    Returns:
        A list of dictionaries representing each line in the JSONL file.
    """
    data = []
    if not os.path.exists(file_path):
        logger.error(f"Dataset file not found at: {file_path}")
        return data

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def main() -> None:
    """Main execution function for initializing the vector database."""
    logger.info("Starting vector database initialization process...")

    # 1. Initialize core services
    embedding_svc = EmbeddingService()
    vector_store = FaissVectorStore(
        dimension=settings.vector_dim,
        index_path=settings.vector_index_path,
        meta_path=settings.knowledge_meta_path,
    )

    # 2. Load raw data
    raw_data = load_jsonl_data(settings.data_path)
    if not raw_data:
        logger.warning("No data loaded. Exiting.")
        return

    logger.info(f"Successfully loaded {len(raw_data)} dialogues.")

    # 3. Process data in batches to prevent Out-Of-Memory (OOM) errors
    batch_size = 64
    # texts_to_embed: List[str] = []
    # metadata_to_store: List[Dict[str, str]] = []

    for i in tqdm(range(0, len(raw_data), batch_size), desc="Processing Batches"):
        batch_items = raw_data[i : i + batch_size]
        batch_texts = []
        batch_meta = []

        for item in batch_items:
            messages = item.get("messages", [])
            user_text = None
            bot_text = None

            # Extract user query and bot response from the ChatML format
            for msg in messages:
                if msg.get("role") == "user":
                    user_text = msg.get("content")
                elif msg.get("role") == "assistant":
                    bot_text = msg.get("content")

            if user_text and bot_text:
                batch_texts.append(user_text)
                # Store the bot's response as metadata to retrieve later
                batch_meta.append({"bot_response": bot_text})

        if batch_texts:
            # Generate embeddings for the user queries
            embeddings = embedding_svc.encode(batch_texts)
            # Add vectors and metadata to the FAISS store
            vector_store.add_texts(texts=batch_texts, embeddings=embeddings, metadata=batch_meta)

    logger.info(f"Vector database initialization complete. Saved to {settings.vector_index_path}")


if __name__ == "__main__":
    main()
