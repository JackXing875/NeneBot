import asyncio

from src.adapters.telegram import TelegramBotRunner
from src.runtime import RuntimeServices
from src.services.session_store import InMemorySessionStore


class FakeTelegramAPI:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
    ) -> None:
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_to_message_id": reply_to_message_id,
            }
        )


class DummyEmbeddingService:
    pass


class DummyVectorStore:
    pass


class DummyRAGPipeline:
    pass


class DummyLLMClient:
    provider_name = "fake"
    model_name = "fake-model"


def build_services() -> RuntimeServices:
    return RuntimeServices(
        embedding_svc=DummyEmbeddingService(),  # type: ignore[arg-type]
        vector_store=DummyVectorStore(),  # type: ignore[arg-type]
        rag_pipeline=DummyRAGPipeline(),  # type: ignore[arg-type]
        llm_client=DummyLLMClient(),  # type: ignore[arg-type]
        session_store=InMemorySessionStore(),
    )


def test_extract_message_returns_normalized_payload() -> None:
    update = {
        "update_id": 1,
        "message": {
            "message_id": 42,
            "text": " 你好 ",
            "chat": {"id": 123456},
        },
    }

    message = TelegramBotRunner._extract_message(update)

    assert message is not None
    assert message.chat_id == 123456
    assert message.message_id == 42
    assert message.text == "你好"
    assert message.session_id == "telegram:123456"


def test_extract_message_ignores_non_text_updates() -> None:
    update = {
        "update_id": 1,
        "message": {
            "message_id": 42,
            "chat": {"id": 123456},
            "photo": [{"file_id": "abc"}],
        },
    }

    assert TelegramBotRunner._extract_message(update) is None


def test_reset_command_clears_session_and_replies() -> None:
    api = FakeTelegramAPI()
    services = build_services()
    services.session_store.add_turn("telegram:123456", "u", "a")
    runner = TelegramBotRunner(api=api, services=services)

    update = {
        "update_id": 1,
        "message": {
            "message_id": 99,
            "text": "/reset",
            "chat": {"id": 123456},
        },
    }

    handled = asyncio.run(runner.handle_update(update))

    assert handled is True
    assert services.session_store.get_history("telegram:123456") == []
    assert api.sent_messages[0]["chat_id"] == 123456
    assert api.sent_messages[0]["reply_to_message_id"] == 99
