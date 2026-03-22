import asyncio

import pytest
from fastapi import HTTPException

from src.adapters.telegram import (
    TelegramBotRunner,
    configure_telegram_delivery,
    validate_telegram_webhook_secret,
)
from src.runtime import RuntimeServices
from src.services.session_store import InMemorySessionStore


class FakeTelegramAPI:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []
        self.webhook_calls: list[dict[str, object]] = []
        self.delete_webhook_calls = 0

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

    async def set_webhook(self, url: str, secret_token: str | None = None) -> None:
        self.webhook_calls.append({"url": url, "secret_token": secret_token})

    async def delete_webhook(self) -> None:
        self.delete_webhook_calls += 1


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


def test_builtin_commands_reply_without_llm_call() -> None:
    api = FakeTelegramAPI()
    services = build_services()
    runner = TelegramBotRunner(api=api, services=services)

    for command in ("/start", "/help", "/model"):
        update = {
            "update_id": 1,
            "message": {
                "message_id": 99,
                "text": command,
                "chat": {"id": 123456},
            },
        }
        handled = asyncio.run(runner.handle_update(update))
        assert handled is True

    assert "可用命令" in str(api.sent_messages[0]["text"])
    assert "使用说明" in str(api.sent_messages[1]["text"])
    assert "当前模型后端" in str(api.sent_messages[2]["text"])


def test_validate_telegram_webhook_secret_allows_matching_secret(monkeypatch) -> None:
    monkeypatch.setattr("src.adapters.telegram.settings.telegram_webhook_secret", "secret-123")
    validate_telegram_webhook_secret("secret-123")


def test_validate_telegram_webhook_secret_rejects_invalid_secret(monkeypatch) -> None:
    monkeypatch.setattr("src.adapters.telegram.settings.telegram_webhook_secret", "secret-123")
    with pytest.raises(HTTPException):
        validate_telegram_webhook_secret("wrong")


def test_configure_telegram_delivery_for_polling_deletes_webhook(monkeypatch) -> None:
    api = FakeTelegramAPI()
    monkeypatch.setattr("src.adapters.telegram.settings.telegram_mode", "polling")

    asyncio.run(configure_telegram_delivery(api))

    assert api.delete_webhook_calls == 1


def test_configure_telegram_delivery_for_webhook_sets_webhook(monkeypatch) -> None:
    api = FakeTelegramAPI()
    monkeypatch.setattr("src.adapters.telegram.settings.telegram_mode", "webhook")
    monkeypatch.setattr(
        "src.adapters.telegram.settings.telegram_public_base_url",
        "https://example.com",
    )
    monkeypatch.setattr("src.adapters.telegram.settings.telegram_webhook_path", "/telegram/webhook")
    monkeypatch.setattr("src.adapters.telegram.settings.telegram_webhook_secret", "secret-123")

    asyncio.run(configure_telegram_delivery(api))

    assert api.webhook_calls == [
        {
            "url": "https://example.com/telegram/webhook",
            "secret_token": "secret-123",
        }
    ]
