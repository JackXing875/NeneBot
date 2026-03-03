"""Global configuration settings for the RAG application.

This module uses Pydantic BaseSettings to manage environment variables
and application configurations, ensuring type safety and validation.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables or defaults."""

    # API Settings
    api_title: str = "Ningning RAG API"
    api_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000

    # Model Settings (Using the lightweight BGE model for embeddings)
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    vector_dim: int = 512  # Dimensionality of bge-small-zh-v1.5 outputs

    # Storage Paths
    data_path: str = "data/raw/train.jsonl"
    vector_index_path: str = "vector_store/faiss_index.bin"
    knowledge_meta_path: str = "vector_store/knowledge_base.json"

    class Config:
        """Pydantic config class for environment variable loading."""
        env_file = ".env"


# Global singleton instance to be imported across the application
settings = Settings()