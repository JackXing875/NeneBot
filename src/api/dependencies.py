"""FastAPI dependency providers – pull services from app.state."""

from fastapi import Request

from src.infrastructure.llm_client import OllamaClient
from src.services.rag_pipeline import RAGPipeline
from src.services.session_store import SessionStore


def get_rag_pipeline(request: Request) -> RAGPipeline:
    return request.app.state.rag_pipeline


def get_llm_client(request: Request) -> OllamaClient:
    return request.app.state.llm_client


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store
