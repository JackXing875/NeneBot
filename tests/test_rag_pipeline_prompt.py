from pathlib import Path

from src.knowledge.pack import validate_character_pack
from src.knowledge.runtime import RuntimeCharacter
from src.services.rag_pipeline import RAGPipeline


class DummyVectorStore:
    def search(self, query_embedding, top_k=3):  # type: ignore[no-untyped-def]
        return []


class DummyEmbeddingService:
    def encode(self, texts, batch_size=32):  # type: ignore[no-untyped-def]
        return [[0.0] * 32 for _ in texts]


def demo_character() -> RuntimeCharacter:
    root = Path(__file__).resolve().parents[1]
    return RuntimeCharacter.from_pack(validate_character_pack(root / "packs" / "demo"))


def build_pipeline() -> RAGPipeline:
    return RAGPipeline(
        vector_store=DummyVectorStore(),  # type: ignore[arg-type]
        embedding_svc=DummyEmbeddingService(),  # type: ignore[arg-type]
        character=demo_character(),
    )


def test_build_messages_uses_pack_prompt_persona_and_provenance() -> None:
    messages = build_pipeline().build_messages(
        query="为什么知识要记录来源？",
        context_results=[
            {
                "record_id": "source-traceability",
                "query_text": "为什么知识要记录来源？",
                "bot_response": "因为来源让内容能够核验。",
                "similarity_score": 0.91,
                "provenance": {
                    "source": "packs/demo/knowledge.jsonl",
                    "license": "CC0-1.0",
                },
            }
        ],
    )

    system_prompt = messages[0]["content"]
    assert messages[0]["role"] == "system"
    assert "原创角色“米拉 / Mira”" in system_prompt
    assert "折光档案馆并非现实组织" in system_prompt
    assert "source-traceability" in system_prompt
    assert "source=packs/demo/knowledge.jsonl" in system_prompt
    assert "license=CC0-1.0" in system_prompt
    assert messages[-1] == {"role": "user", "content": "为什么知识要记录来源？"}


def test_build_messages_includes_response_language_and_history() -> None:
    messages = build_pipeline().build_messages(
        query="please use English",
        context_results=[],
        history=[{"role": "assistant", "content": "之前的回复"}],
        response_language="en",
    )

    assert "本轮使用 English" in messages[0]["content"]
    assert "不要虚构 Pack 事实" in messages[0]["content"]
    assert messages[1] == {"role": "assistant", "content": "之前的回复"}
