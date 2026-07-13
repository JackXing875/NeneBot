import asyncio
import importlib.util
import json
import sys
from collections.abc import AsyncIterator
from types import ModuleType, SimpleNamespace
from typing import Any

import httpx
from fastapi import FastAPI, Request

from src.core.config import settings
from src.core.rate_limit import InMemoryRateLimiter, RateLimitMiddleware
from src.infrastructure.llm_base import BaseLLMClient
from src.services.session_store import InMemorySessionStore


class StubRAGPipeline:
    def process_query(
        self,
        query: str,
        top_k: int = 3,
        history: list[dict[str, str]] | None = None,
        response_language: str = "zh",
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        messages = [{"role": "system", "content": f"stub:{response_language}"}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": query})
        contexts = [
            {
                "query_text": "早上好",
                "bot_response": "早上好，保科君。",
                "similarity_score": 0.91,
            }
        ][:top_k]
        return messages, contexts


class StaticLLMClient(BaseLLMClient):
    provider_name = "static"
    model_name = "static-model"

    async def chat_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        yield "stub-"
        yield "reply"


class InterruptingLLMClient(BaseLLMClient):
    provider_name = "interrupting"
    model_name = "interrupting-model"

    async def chat_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        yield "partial"
        raise RuntimeError("provider interrupted")


class BlockingProviderStream:
    def __init__(self) -> None:
        self._first_chunk_sent = False
        self._block = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.closed = asyncio.Event()

    def __aiter__(self) -> "BlockingProviderStream":
        return self

    async def __anext__(self) -> str:
        if not self._first_chunk_sent:
            self._first_chunk_sent = True
            return "first"
        try:
            await self._block.wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.closed.set()


class DisconnectAwareLLMClient(BaseLLMClient):
    provider_name = "disconnect-aware"
    model_name = "disconnect-aware-model"

    def __init__(self, stream: BlockingProviderStream) -> None:
        self.stream = stream

    def chat_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        return self.stream


def build_chat_app(
    llm: BaseLLMClient,
    sessions: InMemorySessionStore,
    *,
    limiter: InMemoryRateLimiter | None = None,
) -> FastAPI:
    # The route only needs the RAG interface. Keep this ASGI test independent
    # from the heavyweight local embedding runtime when optional wheels are not
    # installed in a minimal test environment.
    if "torch" not in sys.modules and importlib.util.find_spec("torch") is None:
        torch_module = ModuleType("torch")
        torch_module.__dict__["cuda"] = SimpleNamespace(is_available=lambda: False)
        sys.modules["torch"] = torch_module
    if (
        "sentence_transformers" not in sys.modules
        and importlib.util.find_spec("sentence_transformers") is None
    ):
        sentence_transformers_module = ModuleType("sentence_transformers")
        sentence_transformers_module.__dict__["SentenceTransformer"] = object
        sys.modules["sentence_transformers"] = sentence_transformers_module

    from src.api.dependencies import get_llm_client, get_rag_pipeline, get_session_store
    from src.api.routers import chat_router, get_http_request

    app = FastAPI()
    rag = StubRAGPipeline()
    app.state.rag_pipeline = rag
    app.state.llm_client = llm
    app.state.session_store = sessions

    async def override_rag() -> StubRAGPipeline:
        return rag

    async def override_llm() -> BaseLLMClient:
        return llm

    async def override_sessions() -> InMemorySessionStore:
        return sessions

    async def override_http_request(request: Request) -> Request:
        return request

    app.dependency_overrides[get_rag_pipeline] = override_rag
    app.dependency_overrides[get_llm_client] = override_llm
    app.dependency_overrides[get_session_store] = override_sessions
    app.dependency_overrides[get_http_request] = override_http_request
    app.include_router(chat_router)
    if limiter is not None:
        app.add_middleware(RateLimitMiddleware, limiter=limiter)
    return app


async def post_json(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await asyncio.wait_for(
            client.post(path, json={"query": "早上好", "top_k": 1}),
            timeout=2,
        )


def parse_sse_events(response: httpx.Response) -> list[dict[str, Any]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_auth_disabled_allows_real_v1_request(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", False)
    sessions = InMemorySessionStore(max_history=6)
    app = build_chat_app(StaticLLMClient(), sessions)

    response = asyncio.run(post_json(app, "/v1/chat"))

    assert response.status_code == 200
    assert response.json()["reply"] == "stub-reply"


def test_stream_emits_meta_chunks_and_done_over_asgi(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", False)
    sessions = InMemorySessionStore(max_history=6)
    app = build_chat_app(StaticLLMClient(), sessions)

    response = asyncio.run(post_json(app, "/v1/chat/stream"))
    events = parse_sse_events(response)

    assert response.status_code == 200
    assert [event["type"] for event in events] == ["meta", "chunk", "chunk", "done"]
    assert "".join(event.get("content", "") for event in events) == "stub-reply"
    session_id = str(events[0]["session_id"])
    assert sessions.get_history(session_id)[-1] == {
        "role": "assistant",
        "content": "stub-reply",
    }


def test_provider_interruption_emits_error_and_done_without_persisting(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", False)
    sessions = InMemorySessionStore(max_history=6)
    app = build_chat_app(InterruptingLLMClient(), sessions)

    response = asyncio.run(post_json(app, "/v1/chat/stream"))
    events = parse_sse_events(response)

    assert response.status_code == 200
    assert [event["type"] for event in events] == ["meta", "chunk", "error", "done"]
    session_id = str(events[0]["session_id"])
    assert sessions.get_history(session_id) == []


def test_client_disconnect_closes_provider_stream(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", False)

    async def run_request() -> tuple[BlockingProviderStream, InMemorySessionStore]:
        stream = BlockingProviderStream()
        sessions = InMemorySessionStore(max_history=6)
        app = build_chat_app(DisconnectAwareLLMClient(stream), sessions)
        request_body = json.dumps({"query": "早上好", "top_k": 1}).encode()
        request_consumed = False
        disconnect = asyncio.Event()

        async def receive() -> dict[str, object]:
            nonlocal request_consumed
            if not request_consumed:
                request_consumed = True
                return {
                    "type": "http.request",
                    "body": request_body,
                    "more_body": False,
                }
            await disconnect.wait()
            return {"type": "http.disconnect"}

        async def send(message: dict[str, Any]) -> None:
            if message["type"] != "http.response.body":
                return
            body = message.get("body", b"")
            if isinstance(body, bytes) and b'"type": "chunk"' in body:
                disconnect.set()

        scope: dict[str, Any] = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/v1/chat/stream",
            "raw_path": b"/v1/chat/stream",
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"testserver"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(request_body)).encode()),
            ],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }

        await asyncio.wait_for(app(scope, receive, send), timeout=1)
        await asyncio.wait_for(stream.cancelled.wait(), timeout=1)
        await asyncio.wait_for(stream.closed.wait(), timeout=1)
        return stream, sessions

    stream, sessions = asyncio.run(run_request())

    assert stream.cancelled.is_set()
    assert stream.closed.is_set()
    assert not sessions._sessions


def test_rate_limit_returns_429_instead_of_500_over_asgi(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", False)
    sessions = InMemorySessionStore(max_history=6)
    app = build_chat_app(
        StaticLLMClient(),
        sessions,
        limiter=InMemoryRateLimiter(limit=1, window_seconds=60),
    )

    async def make_requests() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            first = await client.post("/v1/chat", json={"query": "第一次"})
            limited = await client.post("/v1/chat", json={"query": "第二次"})
            return first, limited

    first, limited = asyncio.run(make_requests())

    assert first.status_code == 200
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert limited.headers["Retry-After"] == "60"
