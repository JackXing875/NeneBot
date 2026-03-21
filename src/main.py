"""FastAPI application entry point with lifespan service initialization."""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.routers import chat_router
from src.core.config import settings
from src.core.exceptions import NeneBotError
from src.core.http import (
    RequestContextMiddleware,
    http_exception_handler,
    nenebot_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from src.core.logger import setup_logger
from src.core.observability import build_health_payload, build_liveness_payload
from src.infrastructure.llm_base import BaseLLMClient
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.services.embedding_svc import EmbeddingService
from src.services.rag_pipeline import RAGPipeline
from src.services.session_store import InMemorySessionStore, SessionStore
from src.services.session_store_redis import RedisSessionStore

logger = setup_logger()


def _create_llm_client() -> BaseLLMClient:
    """Factory: return the correct LLM client based on LLM_PROVIDER env var."""
    provider = settings.llm_provider.lower()
    logger.info(f"LLM provider: {provider}")

    if provider == "claude":
        from src.infrastructure.llm_claude import ClaudeClient
        return ClaudeClient()

    if provider in ("deepseek", "openai"):
        from src.infrastructure.llm_openai_compat import OpenAICompatClient
        return OpenAICompatClient()

    # Default: Ollama (local)
    from src.infrastructure.llm_client import OllamaClient
    return OllamaClient()


def _create_session_store() -> SessionStore:
    """Create the configured session backend with a safe in-memory fallback."""
    backend = settings.session_backend.lower()
    if backend == "redis":
        try:
            store = RedisSessionStore(
                redis_url=settings.redis_url,
                max_history=settings.session_max_history,
                ttl_seconds=settings.session_ttl_seconds,
            )
            # Fail fast on invalid connection details; fallback to memory in local dev.
            store.client.ping()
            logger.info("Session backend: redis")
            return store
        except Exception as exc:
            logger.warning(f"Redis session store unavailable, falling back to memory: {exc}")

    logger.info("Session backend: memory")
    return InMemorySessionStore(max_history=settings.session_max_history)


def _check_session_backend(store: SessionStore) -> tuple[bool, str | None]:
    """Return backend health for the session store."""
    if getattr(store, "backend_name", "memory") != "redis":
        return True, None

    try:
        if isinstance(store, RedisSessionStore):
            store.ping()
        return True, None
    except Exception as exc:
        return False, str(exc)


def _ensure_index_exists() -> None:
    """Build the FAISS vector index on first run (e.g. fresh Railway deploy)."""
    index_path = Path(settings.vector_index_path)
    meta_path = Path(settings.knowledge_meta_path)

    if index_path.exists() and meta_path.exists():
        return

    logger.info("Vector index not found – building from scratch (this may take a minute)...")
    # Import here to avoid circular deps at module load time
    from scripts.init_vector_db import main as build_index  # type: ignore[import]
    build_index()
    logger.info("Vector index build complete.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize all services on startup; release resources on shutdown."""
    logger.info("NeneBot starting up…")

    _ensure_index_exists()

    app.state.embedding_svc = EmbeddingService()
    app.state.vector_store = FaissVectorStore(
        dimension=settings.vector_dim,
        index_path=settings.vector_index_path,
        meta_path=settings.knowledge_meta_path,
    )
    app.state.rag_pipeline = RAGPipeline(
        vector_store=app.state.vector_store,
        embedding_svc=app.state.embedding_svc,
    )
    app.state.llm_client = _create_llm_client()
    app.state.session_store = _create_session_store()

    logger.info("All services ready.")
    yield
    logger.info("NeneBot shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description="RAG-powered conversational API for Ayachi Nene.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(NeneBotError, nenebot_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # API routes
    app.include_router(chat_router)

    @app.get("/health", tags=["Ops"])
    async def health_check() -> dict[str, object]:
        vs: FaissVectorStore = app.state.vector_store
        session_store: SessionStore = app.state.session_store
        frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
        session_ok, session_error = _check_session_backend(session_store)
        return build_health_payload(
            vector_store=vs,
            frontend_dist_exists=frontend_dist.exists(),
            session_backend_name=getattr(session_store, "backend_name", "unknown"),
            session_backend_ok=session_ok,
            session_backend_error=session_error,
        )

    @app.get("/health/live", tags=["Ops"])
    async def liveness_check() -> dict[str, object]:
        return build_liveness_payload()

    @app.get("/health/ready", tags=["Ops"])
    async def readiness_check() -> JSONResponse:
        payload = await health_check()
        status_code = 200 if bool(payload.get("ready")) else 503
        return JSONResponse(status_code=status_code, content=payload)

    # Serve compiled Vue frontend if the dist directory exists.
    # In production (Railway), the build step creates frontend/dist before uvicorn starts.
    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
        logger.info(f"Serving frontend from {frontend_dist}")
    else:
        logger.info("frontend/dist not found – skipping static file serving (dev mode).")

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=True)
