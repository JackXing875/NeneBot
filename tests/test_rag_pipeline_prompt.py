from src.services.rag_pipeline import RAGPipeline


class DummyVectorStore:
    def search(self, query_embedding, top_k=3):  # type: ignore[no-untyped-def]
        return []


class DummyEmbeddingService:
    def encode(self, texts, batch_size=32):  # type: ignore[no-untyped-def]
        return [[0.0] * 512 for _ in texts]


def test_build_messages_uses_nene_character_card_and_reference_block() -> None:
    pipeline = RAGPipeline(
        vector_store=DummyVectorStore(),  # type: ignore[arg-type]
        embedding_svc=DummyEmbeddingService(),  # type: ignore[arg-type]
    )

    messages = pipeline.build_messages(
        query="今天有点累",
        context_results=[
            {
                "query_text": "今天有点累",
                "bot_response": "如果累了的话，就先休息一下吧，保科君。",
                "similarity_score": 0.91,
            }
        ],
    )

    assert messages[0]["role"] == "system"
    assert "绫地宁宁" in messages[0]["content"]
    assert "不直接照搬" in messages[0]["content"]
    assert "参考样本" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "今天有点累"}
