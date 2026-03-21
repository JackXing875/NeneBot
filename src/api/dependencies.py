"""FastAPI dependency providers – pull services from app.state."""

from typing import cast

from fastapi import Request

from src.infrastructure.llm_base import BaseLLMClient
from src.services.rag_pipeline import RAGPipeline
from src.services.session_store import SessionStore


def get_rag_pipeline(request: Request) -> RAGPipeline:
    return cast(RAGPipeline, request.app.state.rag_pipeline)


def get_llm_client(request: Request) -> BaseLLMClient:
    return cast(BaseLLMClient, request.app.state.llm_client)


def get_session_store(request: Request) -> SessionStore:
    return cast(SessionStore, request.app.state.session_store)
