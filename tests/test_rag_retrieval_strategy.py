from src.services.rag_pipeline import RAGPipeline


class DummyEmbeddingService:
    def encode(self, texts, batch_size=32):  # type: ignore[no-untyped-def]
        return [[0.0] * 512 for _ in texts]


class DummyVectorStore:
    def __init__(self) -> None:
        self.results = [
            {
                "query_text": "今天辛苦了",
                "bot_response": "……那，那个……那个……",
                "similarity_score": 0.82,
                "query_tags": ["comfort"],
                "response_tags": ["shy"],
            },
            {
                "query_text": "今天有点累",
                "bot_response": "如果累了的话，就先休息一下吧，保科君。",
                "similarity_score": 0.79,
                "query_tags": ["comfort"],
                "response_tags": ["comfort", "support", "relationship"],
            },
        ]

    def search(self, query_embedding, top_k=3):  # type: ignore[no-untyped-def]
        return self.results[:top_k]


class LowScoreVectorStore:
    def search(self, query_embedding, top_k=3):  # type: ignore[no-untyped-def]
        return [
            {
                "query_text": "完全无关的问题",
                "bot_response": "不应该进入提示词的低分答案",
                "similarity_score": 0.2,
                "query_tags": [],
                "response_tags": [],
            }
        ]


def test_rag_pipeline_reranks_by_intent_and_response_quality() -> None:
    pipeline = RAGPipeline(
        vector_store=DummyVectorStore(),  # type: ignore[arg-type]
        embedding_svc=DummyEmbeddingService(),  # type: ignore[arg-type]
    )

    results = pipeline.retrieve_and_filter("今天有点累", top_k=1)

    assert len(results) == 1
    assert results[0]["bot_response"] == "如果累了的话，就先休息一下吧，保科君。"
    assert results[0]["rerank_score"] > 0.79


def test_rag_pipeline_returns_no_context_below_similarity_threshold() -> None:
    pipeline = RAGPipeline(
        vector_store=LowScoreVectorStore(),  # type: ignore[arg-type]
        embedding_svc=DummyEmbeddingService(),  # type: ignore[arg-type]
    )

    results = pipeline.retrieve_and_filter("今天有点累", top_k=1)

    assert results == []


class RelationshipNoiseVectorStore:
    def __init__(self) -> None:
        self.results = [
            {
                "query_text": "喜欢你……嗯嗯、超级喜欢……嗯啾噜、啾、啾",
                "bot_response": (
                    "呼噜呼噜……嗯呜呜、我也、我也喜欢你、非常喜欢……"
                    "啾、呼噜呼噜呼噜、啾、啾、啾————……"
                ),
                "similarity_score": 0.86,
                "query_tags": ["relationship", "confession", "intimate_noise"],
                "response_tags": ["relationship", "confession", "intimate_noise"],
            },
            {
                "query_text": "你会不会也有一点在意我",
                "bot_response": (
                    "那个……突然这么问，我会有点困扰。不过，如果对象是保科君的话，我当然会在意。"
                ),
                "similarity_score": 0.72,
                "query_tags": ["relationship", "shy"],
                "response_tags": ["relationship", "shy"],
            },
        ]

    def search(self, query_embedding, top_k=3):  # type: ignore[no-untyped-def]
        return self.results[:top_k]


class WitchIntentVectorStore:
    def __init__(self) -> None:
        self.results = [
            {
                "query_text": "应该……就是魔女了吧？",
                "bot_response": "大概……不，不过，怎么会，那样的居然是魔女……？",
                "similarity_score": 0.8,
                "query_tags": ["shy"],
                "response_tags": ["shy"],
            },
            {
                "query_text": "你是不是魔女",
                "bot_response": (
                    "那个……现在突然问这个，我有点不知道该怎么回答。不过，这件事还请先替我保密。"
                ),
                "similarity_score": 0.72,
                "query_tags": ["witch", "shy"],
                "response_tags": ["witch", "shy"],
            },
        ]

    def search(self, query_embedding, top_k=3):  # type: ignore[no-untyped-def]
        return self.results[:top_k]


def test_rag_pipeline_penalizes_intimate_noise_hits_for_regular_affection_queries() -> None:
    pipeline = RAGPipeline(
        vector_store=RelationshipNoiseVectorStore(),  # type: ignore[arg-type]
        embedding_svc=DummyEmbeddingService(),  # type: ignore[arg-type]
    )

    results = pipeline.retrieve_and_filter("你是不是有点喜欢我", top_k=1)

    assert len(results) == 1
    assert "在意" in results[0]["bot_response"]
    assert "intimate_noise" not in results[0].get("response_tags", [])


def test_rag_pipeline_prefers_witch_specific_contexts_for_secret_queries() -> None:
    pipeline = RAGPipeline(
        vector_store=WitchIntentVectorStore(),  # type: ignore[arg-type]
        embedding_svc=DummyEmbeddingService(),  # type: ignore[arg-type]
    )

    results = pipeline.retrieve_and_filter("你是不是魔女", top_k=1)

    assert len(results) == 1
    assert "保密" in results[0]["bot_response"]
    assert "witch" in results[0].get("response_tags", [])
