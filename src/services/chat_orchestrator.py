"""Reusable chat orchestration shared by API routes and adapters."""

from dataclasses import dataclass
from typing import Any

from src.infrastructure.llm_base import BaseLLMClient
from src.services.rag_pipeline import RAGPipeline
from src.services.session_store import SessionStore


@dataclass
class ChatTurnResult:
    """Result of a single user turn."""

    reply: str
    session_id: str
    contexts: list[dict[str, Any]]
    messages: list[dict[str, str]]


async def generate_chat_turn(
    *,
    query: str,
    session_id: str | None,
    top_k: int,
    rag: RAGPipeline,
    llm: BaseLLMClient,
    sessions: SessionStore,
) -> ChatTurnResult:
    """Execute one full chat turn and persist session history."""
    effective_session_id = sessions.get_or_create(session_id)
    history = sessions.get_history(effective_session_id)
    messages, contexts = rag.process_query(query, top_k, history)
    reply = await llm.chat(messages)
    sessions.add_turn(effective_session_id, query, reply)

    return ChatTurnResult(
        reply=reply,
        session_id=effective_session_id,
        contexts=contexts,
        messages=messages,
    )
