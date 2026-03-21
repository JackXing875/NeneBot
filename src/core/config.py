"""Global configuration settings for the RAG application.

This module uses Pydantic BaseSettings to manage environment variables
and application configurations, ensuring type safety and validation.

LLM Provider selection
----------------------
Set the LLM_PROVIDER environment variable to switch backends:

    LLM_PROVIDER=ollama    → local Ollama (default, for development)
    LLM_PROVIDER=claude    → Anthropic Claude API (requires ANTHROPIC_API_KEY)
    LLM_PROVIDER=deepseek  → DeepSeek API (requires OPENAI_COMPAT_API_KEY)
    LLM_PROVIDER=openai    → Any OpenAI-compatible endpoint
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables or defaults."""

    # --- API ---
    api_title: str = "NeneBot API"
    api_version: str = "2.0.0"
    host: str = "0.0.0.0"
    port: int = 8000  # Overridden by PORT env var on Railway

    # --- Embedding Model ---
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    vector_dim: int = 512

    # --- LLM Provider ---
    # One of: "ollama" | "claude" | "deepseek" | "openai"
    llm_provider: str = "ollama"

    # Ollama (local dev)
    ollama_base_url: str = "http://127.0.0.1:11434"
    llm_model_name: str = "qwen2.5"

    # Claude (Anthropic)
    anthropic_api_key: Optional[str] = None
    claude_model_name: str = "claude-haiku-4-5-20251001"

    # OpenAI-compatible (DeepSeek / Qwen-API / etc.)
    openai_compat_api_key: Optional[str] = None
    openai_compat_base_url: str = "https://api.deepseek.com"
    openai_compat_model: str = "deepseek-chat"

    # --- Storage Paths ---
    data_path: str = str(PROJECT_ROOT / "data" / "raw" / "train.jsonl")
    vector_index_path: str = str(PROJECT_ROOT / "vector_store" / "faiss_index.bin")
    knowledge_meta_path: str = str(PROJECT_ROOT / "vector_store" / "knowledge_base.json")

    # --- RAG ---
    match_threshold: float = 0.55  # Cosine similarity cutoff (0–1)

    # --- Session Memory ---
    session_max_history: int = 20  # Max messages (user+assistant) kept per session
    session_backend: str = "memory"  # "memory" | "redis"
    redis_url: str = "redis://127.0.0.1:6379/0"
    session_ttl_seconds: int = 86400

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
