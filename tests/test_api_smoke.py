import asyncio

from src.api.routers import character_endpoint, chat_endpoint, chat_stream_endpoint
from src.api.schemas import ChatRequest
from src.knowledge.runtime import RuntimeCharacter


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


def test_character_endpoint_exposes_active_pack_metadata() -> None:
    character = RuntimeCharacter(
        schema_version=1,
        pack_id="mira-demo",
        pack_version="1.0.0",
        pack_content_hash="a" * 64,
        display_name="米拉 / Mira",
        default_locale="zh-CN",
        prompt="Be helpful.",
        persona="An original guide.",
        theme={
            "schema_version": 1,
            "primary_color": "#7C83FD",
            "accent_color": "#5EEAD4",
            "background_color": "#111827",
            "avatar": {"kind": "initials", "text": "M"},
        },
        provenance={
            "creator": "Persona Studio contributors",
            "source": "Original demo",
            "license": "CC0-1.0",
            "rights": "owned",
        },
    )

    payload = asyncio.run(character_endpoint(character)).model_dump(mode="json")

    assert payload["pack_id"] == "mira-demo"
    assert payload["theme"]["avatar"]["text"] == "M"
    assert payload["provenance"]["license"] == "CC0-1.0"
