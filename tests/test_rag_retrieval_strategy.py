from pathlib import Path

from src.knowledge.pack import validate_character_pack
from src.knowledge.runtime import RuntimeCharacter
from src.services.rag_pipeline import RAGPipeline


class DummyEmbeddingService:
    def encode(self, texts, batch_size=32):  # type: ignore[no-untyped-def]
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class ResultVectorStore:
    def __init__(self, results):  # type: ignore[no-untyped-def]
        self.results = results

    def search(self, query_embedding, top_k=3):  # type: ignore[no-untyped-def]
        return self.results[:top_k]


def demo_character() -> RuntimeCharacter:
    root = Path(__file__).resolve().parents[1]
    return RuntimeCharacter.from_pack(validate_character_pack(root / "packs" / "demo"))


def build_pipeline(results) -> RAGPipeline:  # type: ignore[no-untyped-def]
    return RAGPipeline(
        vector_store=ResultVectorStore(results),  # type: ignore[arg-type]
        embedding_svc=DummyEmbeddingService(),  # type: ignore[arg-type]
        character=demo_character(),
    )


def test_rag_pipeline_prefers_exact_reviewed_record() -> None:
    pipeline = build_pipeline(
        [
            {
                "record_id": "related",
                "query_text": "知识来源是什么？",
                "bot_response": "相关回答",
                "similarity_score": 0.82,
            },
            {
                "record_id": "exact",
                "query_text": "为什么知识要记录来源？",
                "bot_response": "精确回答",
                "similarity_score": 0.78,
            },
        ]
    )

    results = pipeline.retrieve_and_filter("为什么知识要记录来源？", top_k=1)

    assert results[0]["record_id"] == "exact"
    assert results[0]["rerank_score"] > results[0]["similarity_score"]


def test_rag_pipeline_returns_no_context_below_similarity_threshold() -> None:
    pipeline = build_pipeline(
        [
            {
                "record_id": "low",
                "query_text": "完全无关的问题",
                "bot_response": "不应该进入提示词",
                "similarity_score": 0.2,
            }
        ]
    )

    assert pipeline.retrieve_and_filter("今天有点累", top_k=1) == []


def test_rag_pipeline_preserves_record_provenance() -> None:
    provenance = {
        "creator": "Persona Studio contributors",
        "source": "packs/demo/knowledge.jsonl",
        "license": "CC0-1.0",
        "rights": "owned",
    }
    pipeline = build_pipeline(
        [
            {
                "record_id": "privacy-boundary",
                "query_text": "你会记住我的秘密吗？",
                "bot_response": "不会主动索取秘密。",
                "similarity_score": 0.9,
                "provenance": provenance,
            }
        ]
    )

    results = pipeline.retrieve_and_filter("你会记住我的秘密吗？", top_k=1)

    assert results[0]["provenance"] == provenance
