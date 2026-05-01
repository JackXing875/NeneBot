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

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

LLMProvider = Literal["ollama", "claude", "deepseek", "openai"]


def resolve_env_files() -> tuple[str, ...]:
    """Return layered env files based on APP_ENV."""
    app_env = os.getenv("APP_ENV", "dev").strip().lower() or "dev"
    return (".env", f".env.{app_env}")


def resolve_llm_model_name() -> str:
    """Resolve the effective model name for the active LLM provider."""
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower() or "ollama"
    if provider == "claude":
        return os.getenv("CLAUDE_MODEL_NAME", "claude-haiku-4-5-20251001")
    if provider in ("deepseek", "openai"):
        return os.getenv("OPENAI_COMPAT_MODEL", "deepseek-chat")
    return os.getenv("LLM_MODEL_NAME", "qwen2.5")


class Settings(BaseSettings):
    """Application settings loaded from environment variables or defaults."""

    model_config = SettingsConfigDict(
        env_file=resolve_env_files(),
        env_file_encoding="utf-8",
    )

    app_env: str = "dev"  # dev | staging | prod

    # --- API ---
    api_title: str = "NeneBot API"
    api_version: str = "0.7.0b1"
    host: str = "0.0.0.0"
    port: int = 8000  # Overridden by PORT env var on Railway
    cors_allow_origins: str = "*"  # Comma-separated origins or "*" for all
    max_knowledge_import_bytes: int = 2_097_152  # 2 MiB limit for knowledge import
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # --- Embedding Model ---
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    vector_dim: int = 512

    # --- LLM Provider ---
    llm_provider: LLMProvider = "ollama"

    # Ollama (local dev)
    ollama_base_url: str = "http://127.0.0.1:11434"
    llm_model_name: str = "qwen2.5"
    llm_temperature_ollama: float = 0.7
    llm_top_p_ollama: float = 0.9

    # Claude (Anthropic)
    anthropic_api_key: Optional[str] = None
    claude_model_name: str = "claude-haiku-4-5-20251001"
    llm_temperature_claude: float = 1.0
    llm_max_tokens_claude: int = 512

    # OpenAI-compatible (DeepSeek / Qwen-API / etc.)
    openai_compat_api_key: Optional[str] = None
    openai_compat_base_url: str = "https://api.deepseek.com"
    openai_compat_model: str = "deepseek-chat"
    llm_temperature_openai: float = 0.7
    llm_max_tokens_openai: int = 512

    # --- Storage Paths ---
    data_path: str = str(PROJECT_ROOT / "data" / "raw" / "train.jsonl")
    vector_index_path: str = str(PROJECT_ROOT / "vector_store" / "faiss_index.bin")
    knowledge_meta_path: str = str(PROJECT_ROOT / "vector_store" / "knowledge_base.json")
    frontend_dist_dir: str = str(PROJECT_ROOT / "frontend" / "dist")

    # --- RAG ---
    match_threshold: float = 0.55  # Cosine similarity cutoff (0–1)

    # --- Session Memory ---
    session_max_history: int = 20  # Max messages (user+assistant) kept per session
    session_backend: str = "memory"  # "memory" | "redis"
    redis_url: str = "redis://127.0.0.1:6379/0"
    session_ttl_seconds: int = 86400

    # --- Reliability / Limits ---
    api_rate_limit_count: int = 20
    api_rate_limit_window_seconds: int = 60
    api_auth_enabled: bool = False
    api_auth_tokens: str = ""
    api_auth_registry_path: str = str(PROJECT_ROOT / "config" / "api_tokens.json")
    api_auth_header_name: str = "Authorization"
    tracing_enabled: bool = False
    tracing_service_name: str = "nenebot"
    tracing_exporter: str = "console"  # console | noop
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 2
    metrics_enabled: bool = True

    # --- Telegram Adapter ---
    telegram_bot_token: Optional[str] = None
    telegram_mode: str = "polling"  # "polling" | "webhook"
    telegram_poll_timeout: int = 30
    telegram_top_k: int = 3
    telegram_webhook_path: str = "/integrations/telegram/webhook"
    telegram_webhook_secret: Optional[str] = None
    telegram_public_base_url: Optional[str] = None

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _normalize_llm_provider(cls, v: object) -> str:
        """Normalize to lowercase so `DeepSeek` and `DEEPSEEK` both match the Literal."""
        return str(v).strip().lower() if isinstance(v, str) else str(v)

    @property
    def effective_llm_model(self) -> str:
        """Return the resolved model name for the active provider."""
        if self.llm_provider == "claude":
            return self.claude_model_name
        if self.llm_provider in ("deepseek", "openai"):
            return self.openai_compat_model
        return self.llm_model_name

    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins into a list for starlette middleware."""
        raw = self.cors_allow_origins.strip()
        if raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


settings = Settings()
