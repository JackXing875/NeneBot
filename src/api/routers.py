"""API routers for chat endpoints (streaming + non-streaming)."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from src.api.dependencies import get_llm_client, get_rag_pipeline, get_session_store
from src.api.schemas import ChatRequest, ChatResponse, ReferenceMeta
from src.core.audit import audit_log
from src.core.auth import require_api_scope
from src.core.metrics import llm_request_duration_ms, llm_requests_total
from src.core.observability import now_ms
from src.infrastructure.llm_base import BaseLLMClient
from src.services.chat_orchestrator import generate_chat_turn, prepare_chat_turn
from src.services.rag_pipeline import RAGPipeline
from src.services.session_store import SessionStore

logger = logging.getLogger(__name__)

chat_router = APIRouter(
    prefix="/v1",
    tags=["Chat"],
    dependencies=[Depends(require_api_scope("chat"))],
)


def get_http_request(request: Request) -> Request:
    return request


def resolve_http_request(request: Request | object | None) -> Request | None:
    return request if isinstance(request, Request) else None


@chat_router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    rag: RAGPipeline = Depends(get_rag_pipeline),  # noqa: B008
    llm: BaseLLMClient = Depends(get_llm_client),  # noqa: B008
    sessions: SessionStore = Depends(get_session_store),  # noqa: B008
    http_request: Request = Depends(get_http_request),  # noqa: B008
) -> ChatResponse:
    """Non-streaming chat – waits for the full reply before responding."""
    started_at = now_ms()
    resolved_request = resolve_http_request(http_request)
    audit_log(
        "audit_chat_requested",
        request=resolved_request,
        action="chat_completion",
        endpoint="/v1/chat",
        session_id=request.session_id or "new",
        query_length=len(request.query),
        top_k=request.top_k,
    )
    result = await generate_chat_turn(
        query=request.query,
        session_id=request.session_id,
        top_k=request.top_k,
        rag=rag,
        llm=llm,
        sessions=sessions,
    )
    duration_ms = round(now_ms() - started_at, 2)
    provider_name = getattr(llm, "provider_name", llm.__class__.__name__)
    model_name = getattr(llm, "model_name", getattr(llm, "model", None))
    llm_requests_total.inc(provider_name=provider_name, mode="non_stream")
    llm_request_duration_ms.observe(duration_ms, provider_name=provider_name, mode="non_stream")
    audit_log(
        "llm_completion_completed",
        request=resolved_request,
        action="chat_completion",
        endpoint="/v1/chat",
        mode="non_stream",
        provider_name=provider_name,
        model_name=model_name,
        prompt_messages=len(result.messages),
        output_chars=len(result.reply),
        duration_ms=duration_ms,
        session_id=result.session_id,
    )

    refs = [
        ReferenceMeta(
            historical_query=c.get("query_text", ""),
            bot_response=c.get("bot_response", ""),
            similarity_score=c.get("similarity_score", 0.0),
        )
        for c in result.contexts
    ]
    return ChatResponse(reply=result.reply, session_id=result.session_id, references=refs)


@chat_router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    rag: RAGPipeline = Depends(get_rag_pipeline),  # noqa: B008
    llm: BaseLLMClient = Depends(get_llm_client),  # noqa: B008
    sessions: SessionStore = Depends(get_session_store),  # noqa: B008
    http_request: Request = Depends(get_http_request),  # noqa: B008
) -> StreamingResponse:
    """SSE streaming chat – pushes tokens as they arrive from the LLM.

    Event types:
        meta  – {"type":"meta", "session_id":"...", "references":[...]}
        chunk – {"type":"chunk", "content":"..."}
        error – {"type":"error", "message":"..."}
        done  – {"type":"done"}
    """
    prepared = prepare_chat_turn(
        query=request.query,
        session_id=request.session_id,
        top_k=request.top_k,
        rag=rag,
        sessions=sessions,
    )
    session_id = prepared.session_id
    messages = prepared.messages
    contexts = prepared.contexts

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
        resolved_request = resolve_http_request(http_request)
        provider_stream: AsyncIterator[str] | None = None
        error_event: dict[str, str] | None = None
        audit_log(
            "audit_chat_requested",
            request=resolved_request,
            action="chat_stream",
            endpoint="/v1/chat/stream",
            session_id=session_id,
            query_length=len(request.query),
            top_k=request.top_k,
        )
        try:
            meta_event = {
                "type": "meta",
                "session_id": session_id,
                "references": refs_payload,
            }
            yield f"data: {json.dumps(meta_event)}\n\n"

            provider_stream = llm.chat_stream(messages)
            async for chunk in provider_stream:
                chunk_count += 1
                collected.append(chunk)
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

        except asyncio.CancelledError:
            # A disconnected SSE client must cancel the upstream provider call.
            raise
        except Exception:
            logger.exception(
                "llm_stream_failed",
                extra={
                    "event": "llm_stream_failed",
                    "action": "chat_stream",
                    "endpoint": "/v1/chat/stream",
                    "mode": "stream",
                    "provider_name": getattr(llm, "provider_name", llm.__class__.__name__),
                    "model_name": getattr(llm, "model_name", getattr(llm, "model", None)),
                    "prompt_messages": len(messages),
                    "chunk_count": chunk_count,
                    "output_chars": len("".join(collected)),
                    "duration_ms": round(now_ms() - started_at, 2),
                    "session_id": session_id,
                    "auth_subject": getattr(
                        getattr(resolved_request, "state", None),
                        "auth_subject",
                        None,
                    ),
                },
            )
            error_event = {
                "type": "error",
                "message": "（宁宁的思绪突然断开了……）",
            }
        else:
            # Only persist the turn when no exception occurred
            sessions.add_turn(session_id, request.query, "".join(collected))
            duration_ms = round(now_ms() - started_at, 2)
            provider_name = getattr(llm, "provider_name", llm.__class__.__name__)
            llm_requests_total.inc(provider_name=provider_name, mode="stream")
            llm_request_duration_ms.observe(
                duration_ms,
                provider_name=provider_name,
                mode="stream",
            )
            audit_log(
                "llm_stream_completed",
                request=resolved_request,
                action="chat_stream",
                endpoint="/v1/chat/stream",
                mode="stream",
                provider_name=provider_name,
                model_name=getattr(llm, "model_name", getattr(llm, "model", None)),
                prompt_messages=len(messages),
                chunk_count=chunk_count,
                output_chars=len("".join(collected)),
                duration_ms=duration_ms,
                session_id=session_id,
            )
        finally:
            if provider_stream is not None:
                close = getattr(provider_stream, "aclose", None)
                if close is not None:
                    try:
                        await close()
                    except Exception:
                        logger.exception("llm_stream_close_failed")

        if error_event is not None:
            yield f"data: {json.dumps(error_event)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
