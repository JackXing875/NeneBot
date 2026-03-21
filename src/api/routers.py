"""API routers for chat endpoints (streaming + non-streaming)."""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.api.dependencies import get_llm_client, get_rag_pipeline, get_session_store
from src.api.schemas import ChatRequest, ChatResponse, ReferenceMeta
from src.core.observability import now_ms
from src.infrastructure.llm_base import BaseLLMClient
from src.services.rag_pipeline import RAGPipeline
from src.services.session_store import SessionStore

logger = logging.getLogger(__name__)

chat_router = APIRouter(prefix="/v1", tags=["Chat"])


@chat_router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    rag: RAGPipeline = Depends(get_rag_pipeline),  # noqa: B008
    llm: BaseLLMClient = Depends(get_llm_client),  # noqa: B008
    sessions: SessionStore = Depends(get_session_store),  # noqa: B008
) -> ChatResponse:
    """Non-streaming chat – waits for the full reply before responding."""
    session_id = sessions.get_or_create(request.session_id)
    history = sessions.get_history(session_id)

    messages, contexts = rag.process_query(request.query, request.top_k, history)
    started_at = now_ms()
    reply = await llm.chat(messages)
    logger.info(
        "llm_completion_completed",
        extra={
            "event": "llm_completion_completed",
            "mode": "non_stream",
            "provider_name": getattr(llm, "provider_name", llm.__class__.__name__),
            "model_name": getattr(llm, "model_name", getattr(llm, "model", None)),
            "prompt_messages": len(messages),
            "output_chars": len(reply),
            "duration_ms": round(now_ms() - started_at, 2),
        },
    )

    sessions.add_turn(session_id, request.query, reply)

    refs = [
        ReferenceMeta(
            historical_query=c.get("query_text", ""),
            bot_response=c.get("bot_response", ""),
            similarity_score=c.get("similarity_score", 0.0),
        )
        for c in contexts
    ]
    return ChatResponse(reply=reply, session_id=session_id, references=refs)


@chat_router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    rag: RAGPipeline = Depends(get_rag_pipeline),  # noqa: B008
    llm: BaseLLMClient = Depends(get_llm_client),  # noqa: B008
    sessions: SessionStore = Depends(get_session_store),  # noqa: B008
) -> StreamingResponse:
    """SSE streaming chat – pushes tokens as they arrive from the LLM.

    Event types:
        meta  – {"type":"meta", "session_id":"...", "references":[...]}
        chunk – {"type":"chunk", "content":"..."}
        error – {"type":"error", "message":"..."}
        done  – {"type":"done"}
    """
    session_id = sessions.get_or_create(request.session_id)
    history = sessions.get_history(session_id)
    messages, contexts = rag.process_query(request.query, request.top_k, history)

    refs_payload = [
        {
            "historical_query": c.get("query_text", ""),
            "bot_response": c.get("bot_response", ""),
            "similarity_score": c.get("similarity_score", 0.0),
        }
        for c in contexts
    ]

    async def event_stream() -> AsyncGenerator[str, None]:
        collected: list[str] = []
        chunk_count = 0
        started_at = now_ms()
        try:
            meta_event = {
                "type": "meta",
                "session_id": session_id,
                "references": refs_payload,
            }
            yield f"data: {json.dumps(meta_event)}\n\n"

            async for chunk in llm.chat_stream(messages):
                chunk_count += 1
                collected.append(chunk)
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

        except Exception as e:
            logger.error(f"event_stream error: {e}")
            logger.exception(
                "llm_stream_failed",
                extra={
                    "event": "llm_stream_failed",
                    "mode": "stream",
                    "provider_name": getattr(llm, "provider_name", llm.__class__.__name__),
                    "model_name": getattr(llm, "model_name", getattr(llm, "model", None)),
                    "prompt_messages": len(messages),
                    "chunk_count": chunk_count,
                    "output_chars": len("".join(collected)),
                    "duration_ms": round(now_ms() - started_at, 2),
                },
            )
            error_event = {
                "type": "error",
                "message": "（宁宁的思绪突然断开了……）",
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        else:
            # Only persist the turn when no exception occurred
            sessions.add_turn(session_id, request.query, "".join(collected))
            logger.info(
                "llm_stream_completed",
                extra={
                    "event": "llm_stream_completed",
                    "mode": "stream",
                    "provider_name": getattr(llm, "provider_name", llm.__class__.__name__),
                    "model_name": getattr(llm, "model_name", getattr(llm, "model", None)),
                    "prompt_messages": len(messages),
                    "chunk_count": chunk_count,
                    "output_chars": len("".join(collected)),
                    "duration_ms": round(now_ms() - started_at, 2),
                },
            )
        finally:
            # 'done' MUST always be sent so the client exits its read loop.
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
