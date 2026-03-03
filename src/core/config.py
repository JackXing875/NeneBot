"""Global configuration settings for the RAG application.

This module uses Pydantic BaseSettings to manage environment variables
and application configurations, ensuring type safety and validation.
"""

from pydantic_settings import BaseSettings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

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

    # Ollama LLM Settings
    ollama_base_url: str = "http://127.0.0.1:11434" 
    llm_model_name: str = "qwen2.5"                 

    # Storage Paths
    data_path: str = str(PROJECT_ROOT / "data" / "raw" / "train.jsonl")  # Make sure the extension matches your actual file
    vector_index_path: str = str(PROJECT_ROOT / "vector_store" / "faiss_index.bin")
    knowledge_meta_path: str = str(PROJECT_ROOT / "vector_store" / "knowledge_base.json")

    class Config:
        """Pydantic config class for environment variable loading."""
        env_file = ".env"


# Global singleton instance to be imported across the application
settings = Settings()