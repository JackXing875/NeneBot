"""FastAPI application entry point with lifespan service initialization."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import chat_router
from src.core.config import settings
from src.core.logger import setup_logger
from src.infrastructure.llm_client import OllamaClient
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.services.embedding_svc import EmbeddingService
from src.services.rag_pipeline import RAGPipeline
from src.services.session_store import SessionStore

logger = setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize all services on startup; release resources on shutdown."""
    logger.info("NeneBot starting up – loading services...")

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
    app.state.llm_client = OllamaClient()
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

    app.include_router(chat_router)

    @app.get("/health", tags=["Ops"])
    async def health_check() -> dict:
        vs: FaissVectorStore = app.state.vector_store
        return {
            "status": "ok",
            "index_vectors": vs.index.ntotal,
            "llm_model": settings.llm_model_name,
            "ollama_url": settings.ollama_base_url,
        }

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=True)
