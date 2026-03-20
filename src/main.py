"""FastAPI application entry point with lifespan service initialization."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routers import chat_router
from src.core.config import settings
from src.core.logger import setup_logger
from src.infrastructure.llm_base import BaseLLMClient
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.services.embedding_svc import EmbeddingService
from src.services.rag_pipeline import RAGPipeline
from src.services.session_store import SessionStore

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
    app.state.session_store = SessionStore(max_history=settings.session_max_history)

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
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(chat_router)

    @app.get("/health", tags=["Ops"])
    async def health_check() -> dict:
        vs: FaissVectorStore = app.state.vector_store
        return {
            "status": "ok",
            "llm_provider": settings.llm_provider,
            "llm_model": (
                settings.claude_model_name
                if settings.llm_provider == "claude"
                else settings.openai_compat_model
                if settings.llm_provider in ("deepseek", "openai")
                else settings.llm_model_name
            ),
            "index_vectors": vs.index.ntotal,
        }

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
