"""Main entry point for the FastAPI application."""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import chat_router
from src.core.config import settings

from src.core.logger import setup_logger

# Initialize the global industrial logger
logger = setup_logger()

def create_app() -> FastAPI:
    logger.info("Initializing NeneBot FastAPI Server...")

def create_app() -> FastAPI:
    """Factory function to create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description="RAG-powered conversational API for Ningning."
    )

    # Configure CORS (Cross-Origin Resource Sharing)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allows all origins in development
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(chat_router)

    return app

# Create the global app instance
app = create_app()

if __name__ == "__main__":
    # Run the server locally
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=True  # Enables hot-reloading during development
    )