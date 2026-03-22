"""Shared runtime bootstrapping for API servers and adapters."""

from dataclasses import dataclass
from pathlib import Path

from src.core.config import settings
from src.core.logger import setup_logger
from src.core.tracing import setup_tracing, tracing_available
from src.infrastructure.llm_base import BaseLLMClient
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.services.embedding_svc import EmbeddingService
from src.services.rag_pipeline import RAGPipeline
from src.services.session_store import InMemorySessionStore, SessionStore
from src.services.session_store_redis import RedisSessionStore

logger = setup_logger()


@dataclass
class RuntimeServices:
    """Container for the core services needed to answer chat requests."""

    embedding_svc: EmbeddingService
    vector_store: FaissVectorStore
    rag_pipeline: RAGPipeline
    llm_client: BaseLLMClient
    session_store: SessionStore


def create_llm_client() -> BaseLLMClient:
    """Return the configured LLM provider client."""
    provider = settings.llm_provider.lower()
    logger.info(f"LLM provider: {provider}")

    if provider == "claude":
        from src.infrastructure.llm_claude import ClaudeClient

        return ClaudeClient()

    if provider in ("deepseek", "openai"):
        from src.infrastructure.llm_openai_compat import OpenAICompatClient

        return OpenAICompatClient()

    from src.infrastructure.llm_client import OllamaClient

    return OllamaClient()


def create_session_store() -> SessionStore:
    """Create the configured session backend with a safe in-memory fallback."""
    backend = settings.session_backend.lower()
    if backend == "redis":
        try:
            store = RedisSessionStore(
                redis_url=settings.redis_url,
                max_history=settings.session_max_history,
                ttl_seconds=settings.session_ttl_seconds,
            )
            store.ping()
            logger.info("Session backend: redis")
            return store
        except Exception as exc:
            logger.warning(f"Redis session store unavailable, falling back to memory: {exc}")

    logger.info("Session backend: memory")
    return InMemorySessionStore(max_history=settings.session_max_history)


def check_session_backend(store: SessionStore) -> tuple[bool, str | None]:
    """Return backend health for the session store."""
    if getattr(store, "backend_name", "memory") != "redis":
        return True, None

    try:
        if isinstance(store, RedisSessionStore):
            store.ping()
        return True, None
    except Exception as exc:
        return False, str(exc)


def ensure_index_exists() -> None:
    """Build the FAISS vector index on first run."""
    index_path = Path(settings.vector_index_path)
    meta_path = Path(settings.knowledge_meta_path)

    if index_path.exists() and meta_path.exists():
        return

    logger.info("Vector index not found – building from scratch (this may take a minute)...")
    from scripts.init_vector_db import main as build_index  # type: ignore[import]

    build_index()
    logger.info("Vector index build complete.")


def build_runtime_services() -> RuntimeServices:
    """Instantiate the core services used by chat endpoints and adapters."""
    if settings.tracing_enabled:
        setup_tracing()
        logger.info(f"Tracing enabled: available={tracing_available()}")

    ensure_index_exists()

    embedding_svc = EmbeddingService()
    vector_store = FaissVectorStore(
        dimension=settings.vector_dim,
        index_path=settings.vector_index_path,
        meta_path=settings.knowledge_meta_path,
    )
    rag_pipeline = RAGPipeline(
        vector_store=vector_store,
        embedding_svc=embedding_svc,
    )
    llm_client = create_llm_client()
    session_store = create_session_store()

    return RuntimeServices(
        embedding_svc=embedding_svc,
        vector_store=vector_store,
        rag_pipeline=rag_pipeline,
        llm_client=llm_client,
        session_store=session_store,
    )
