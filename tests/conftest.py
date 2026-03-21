from collections.abc import AsyncIterator
from typing import Any

import pytest

from src.infrastructure.llm_base import BaseLLMClient
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
from src.services.session_store import InMemorySessionStore


class FakeLLMClient(BaseLLMClient):
    def __init__(self, chunks: list[str] | None = None) -> None:
        self.chunks = chunks or ["stub-reply"]

    async def chat_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        for chunk in self.chunks:
            yield chunk


class FakeRAGPipeline:
    def process_query(
        self,
        query: str,
        top_k: int = 3,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        messages = [{"role": "system", "content": "stub"}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": query})
        contexts = [
            {
                "query_text": "你喜欢吃什么？",
                "bot_response": "我喜欢拉面……",
                "similarity_score": 0.92,
            }
        ][:top_k]
        return messages, contexts


@pytest.fixture
def fake_rag_pipeline() -> FakeRAGPipeline:
    return FakeRAGPipeline()


@pytest.fixture
def fake_llm_client() -> FakeLLMClient:
    return FakeLLMClient(["stub-", "reply"])


@pytest.fixture
def fake_session_store() -> InMemorySessionStore:
    return InMemorySessionStore(max_history=6)


@pytest.fixture
def fake_vector_store(tmp_path) -> FaissVectorStore:
    return FaissVectorStore(
        dimension=512,
        index_path=str(tmp_path / "faiss_index.bin"),
        meta_path=str(tmp_path / "knowledge_base.json"),
    )
