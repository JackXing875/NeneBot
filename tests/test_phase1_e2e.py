import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from src.api.routers import chat_endpoint
from src.api.schemas import ChatRequest
from src.infrastructure.llm_base import BaseLLMClient
from src.knowledge.artifacts import ArtifactStore
from src.knowledge.builder import build_pack_artifact, load_artifact
from src.services.rag_pipeline import RAGPipeline
from src.services.session_store import InMemorySessionStore


class StableEncoder:
    model_name = "test/phase1-e2e"

    def __init__(self, dimension: int = 64) -> None:
        self.dimension = dimension
        self.indices: dict[str, int] = {}

    def encode(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            index = self.indices.setdefault(text, len(self.indices)) % self.dimension
            vector = [0.0] * self.dimension
            vector[index] = 1.0
            vectors.append(vector)
        return vectors


class InspectableLLM(BaseLLMClient):
    provider_name = "phase1-test"
    model_name = "phase1-test"

    async def chat_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        assert "米拉 / Mira" in messages[0]["content"]
        assert "source=packs/demo/knowledge.jsonl" in messages[0]["content"]
        yield "可追溯回复"


def test_demo_pack_build_chat_references_promote_and_rollback(tmp_path: Path) -> None:
    pack_dir = Path(__file__).resolve().parents[1] / "packs" / "demo"
    store_root = tmp_path / "artifacts"
    encoder = StableEncoder()
    first = build_pack_artifact(
        pack_dir,
        store_root,
        encoder,
        artifact_version="1.0.0",
        created_at="2026-07-14T00:00:00Z",
    )
    second = build_pack_artifact(
        pack_dir,
        store_root,
        encoder,
        artifact_version="1.1.0",
        created_at="2026-07-14T01:00:00Z",
    )
    store = ArtifactStore(store_root)
    store.activate("mira-demo", first.manifest.artifact_hash)
    store.activate("mira-demo", second.manifest.artifact_hash)
    loaded = load_artifact(store.resolve_current("mira-demo"))
    rag = RAGPipeline(
        vector_store=loaded.vector_store,
        embedding_svc=encoder,  # type: ignore[arg-type]
        character=loaded.character,
    )

    response = asyncio.run(
        chat_endpoint(
            ChatRequest(query="为什么知识要记录来源？", session_id=None, top_k=1),
            rag=rag,
            llm=InspectableLLM(),
            sessions=InMemorySessionStore(),
        )
    )
    rolled_back = store.rollback("mira-demo")

    assert response.reply == "可追溯回复"
    assert response.references[0].record_id == "source-traceability"
    assert response.references[0].pack_id == "mira-demo"
    assert response.references[0].source == "packs/demo/knowledge.jsonl"
    assert response.references[0].license == "CC0-1.0"
    assert rolled_back.path == first.path
    assert store.resolve_current("mira-demo").path == first.path
