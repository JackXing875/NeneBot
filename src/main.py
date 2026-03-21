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
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.runtime import RuntimeServices, build_runtime_services, check_session_backend
from src.services.session_store import SessionStore

logger = setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize all services on startup; release resources on shutdown."""
    logger.info("NeneBot starting up…")
    services: RuntimeServices = build_runtime_services()
    app.state.embedding_svc = services.embedding_svc
    app.state.vector_store = services.vector_store
    app.state.rag_pipeline = services.rag_pipeline
    app.state.llm_client = services.llm_client
    app.state.session_store = services.session_store

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
        session_ok, session_error = check_session_backend(session_store)
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
