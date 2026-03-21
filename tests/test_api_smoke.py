import asyncio

from src.api.routers import chat_endpoint, chat_stream_endpoint
from src.api.schemas import ChatRequest


def test_chat_endpoint_returns_reply_and_session_id(
    fake_rag_pipeline,
    fake_llm_client,
    fake_session_store,
) -> None:
    payload = asyncio.run(
        chat_endpoint(
            ChatRequest(query="你好", top_k=1),
            rag=fake_rag_pipeline,
            llm=fake_llm_client,
            sessions=fake_session_store,
        )
    ).model_dump()

    assert payload["reply"] == "stub-reply"
    assert payload["session_id"]
    assert payload["references"][0]["historical_query"] == "你喜欢吃什么？"


def test_chat_stream_endpoint_streams_sse_events(
    fake_rag_pipeline,
    fake_llm_client,
    fake_session_store,
) -> None:
    response = asyncio.run(
        chat_stream_endpoint(
            ChatRequest(query="你好", top_k=1),
            rag=fake_rag_pipeline,
            llm=fake_llm_client,
            sessions=fake_session_store,
        )
    )

    async def collect_body() -> str:
        chunks: list[str] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    body = asyncio.run(collect_body())

    assert response.status_code == 200
    assert '"type": "meta"' in body
    assert '"type": "chunk"' in body
    assert '"type": "done"' in body
