"""Reusable chat orchestration shared by API routes and adapters."""

from dataclasses import dataclass
from typing import Any

from src.infrastructure.llm_base import BaseLLMClient
from src.services.language_mode import resolve_reply_language
from src.services.rag_pipeline import RAGPipeline
from src.services.session_store import SessionStore


@dataclass
class ChatTurnResult:
    """Result of a single user turn."""

    reply: str
    session_id: str
    contexts: list[dict[str, Any]]
    messages: list[dict[str, str]]


@dataclass
class PreparedChatTurn:
    """Prepared messages and context before the LLM call starts."""

    session_id: str
    contexts: list[dict[str, Any]]
    messages: list[dict[str, str]]
    response_language: str


def prepare_chat_turn(
    *,
    query: str,
    session_id: str | None,
    top_k: int,
    rag: RAGPipeline,
    sessions: SessionStore,
) -> PreparedChatTurn:
    """Prepare a chat turn, including language preference resolution."""
    effective_session_id = sessions.get_or_create(session_id)
    history = sessions.get_history(effective_session_id)
    stored_language = sessions.get_preferred_language(effective_session_id)
    language_decision = resolve_reply_language(
        query,
        stored_preference=stored_language,
    )
    if language_decision.persist_language != stored_language:
        sessions.set_preferred_language(
            effective_session_id,
            language_decision.persist_language,
        )

    messages, contexts = rag.process_query(
        query,
        top_k,
        history,
        response_language=language_decision.response_language,
    )
    return PreparedChatTurn(
        session_id=effective_session_id,
        contexts=contexts,
        messages=messages,
        response_language=language_decision.response_language,
    )


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
    prepared = prepare_chat_turn(
        query=query,
        session_id=session_id,
        top_k=top_k,
        rag=rag,
        sessions=sessions,
    )
    reply = await llm.chat(prepared.messages)
    sessions.add_turn(prepared.session_id, query, reply)

    return ChatTurnResult(
        reply=reply,
        session_id=prepared.session_id,
        contexts=prepared.contexts,
        messages=prepared.messages,
    )
