"""Telegram long-polling adapter for NeneBot."""

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException

from src.core.config import settings
from src.core.logger import setup_logger
from src.core.observability import now_ms
from src.runtime import RuntimeServices, build_runtime_services
from src.services.chat_orchestrator import generate_chat_turn

logger = setup_logger()


@dataclass
class TelegramMessage:
    """Normalized Telegram message payload."""

    chat_id: int
    message_id: int
    text: str
    session_id: str


class TelegramBotAPI:
    """Thin Telegram Bot API client built on httpx."""

    def __init__(self, token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"

    async def get_updates(self, offset: int | None, timeout: int) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset

        async with httpx.AsyncClient(timeout=timeout + 10) as client:
            response = await client.get(f"{self.base_url}/getUpdates", params=params)
            response.raise_for_status()
            payload = response.json()
            return payload.get("result", [])

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.base_url}/sendMessage", json=payload)
            response.raise_for_status()

    async def set_webhook(self, url: str, secret_token: str | None = None) -> None:
        payload: dict[str, Any] = {"url": url}
        if secret_token:
            payload["secret_token"] = secret_token

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.base_url}/setWebhook", json=payload)
            response.raise_for_status()

    async def delete_webhook(self) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.base_url}/deleteWebhook", json={})
            response.raise_for_status()


class TelegramBotRunner:
    """Poll Telegram updates and route text messages to the chat core."""

    def __init__(self, api: TelegramBotAPI, services: RuntimeServices) -> None:
        self.api = api
        self.services = services
        self.top_k = settings.telegram_top_k

    async def handle_update(self, update: dict[str, Any]) -> bool:
        message = self._extract_message(update)
        if message is None:
            return False

        started_at = now_ms()
        command_reply = self._handle_command(message)
        if command_reply is not None:
            await self.api.send_message(
                message.chat_id,
                command_reply,
                reply_to_message_id=message.message_id,
            )
            logger.info(
                "telegram_update_handled",
                extra={
                    "event": "telegram_update_handled",
                    "mode": "telegram",
                    "provider_name": "telegram",
                    "query_length": len(message.text),
                    "duration_ms": round(now_ms() - started_at, 2),
                    "output_chars": len(command_reply),
                },
            )
            return True

        result = await generate_chat_turn(
            query=message.text,
            session_id=message.session_id,
            top_k=self.top_k,
            rag=self.services.rag_pipeline,
            llm=self.services.llm_client,
            sessions=self.services.session_store,
        )
        await self.api.send_message(
            message.chat_id,
            result.reply,
            reply_to_message_id=message.message_id,
        )
        logger.info(
            "telegram_update_handled",
            extra={
                "event": "telegram_update_handled",
                "mode": "telegram",
                "provider_name": "telegram",
                "query_length": len(message.text),
                "prompt_messages": len(result.messages),
                "retrieved_count": len(result.contexts),
                "duration_ms": round(now_ms() - started_at, 2),
                "output_chars": len(result.reply),
            },
        )
        return True

    async def run_forever(self) -> None:
        """Start polling Telegram updates until interrupted."""
        offset: int | None = None
        logger.info("Telegram bot polling started.")
        while True:
            updates = await self.api.get_updates(offset, settings.telegram_poll_timeout)
            for update in updates:
                offset = int(update["update_id"]) + 1
                try:
                    await self.handle_update(update)
                except Exception:
                    logger.exception(
                        "telegram_update_failed",
                        extra={"event": "telegram_update_failed", "mode": "telegram"},
                    )

    @staticmethod
    def _extract_message(update: dict[str, Any]) -> TelegramMessage | None:
        message = update.get("message")
        if not isinstance(message, dict):
            return None

        text = message.get("text")
        chat = message.get("chat")
        if not isinstance(text, str) or not isinstance(chat, dict):
            return None

        chat_id = chat.get("id")
        message_id = message.get("message_id")
        if not isinstance(chat_id, int) or not isinstance(message_id, int):
            return None

        return TelegramMessage(
            chat_id=chat_id,
            message_id=message_id,
            text=text.strip(),
            session_id=f"telegram:{chat_id}",
        )

    def _handle_command(self, message: TelegramMessage) -> str | None:
        if not message.text.startswith("/"):
            return None

        command = message.text.split()[0].split("@")[0].lower()

        if command == "/start":
            return (
                "你好呀，我是宁宁。\n"
                "直接和我聊天就可以了。\n"
                "可用命令：/help /reset /model"
            )
        if command == "/help":
            return (
                "使用说明：\n"
                "1. 直接发送文字开始聊天\n"
                "2. /reset 清空当前会话记忆\n"
                "3. /model 查看当前模型后端"
            )
        if command == "/reset":
            self.services.session_store.clear(message.session_id)
            return "对话记忆已经清空了，我们重新开始吧……"
        if command == "/model":
            llm = self.services.llm_client
            provider = getattr(llm, "provider_name", llm.__class__.__name__)
            model = getattr(llm, "model_name", getattr(llm, "model", "unknown"))
            return f"当前模型后端：{provider}\n当前模型：{model}"

        return "暂时不支持这个命令，发送 /help 可以查看可用命令。"


def validate_telegram_webhook_secret(header_secret: str | None) -> None:
    """Validate Telegram's webhook secret token header when configured."""
    expected = settings.telegram_webhook_secret
    if not expected:
        return
    if header_secret != expected:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret.")


async def configure_telegram_delivery(api: TelegramBotAPI) -> None:
    """Configure Telegram delivery mode based on settings."""
    mode = settings.telegram_mode.lower()
    if mode == "webhook":
        if not settings.telegram_public_base_url:
            raise RuntimeError("TELEGRAM_PUBLIC_BASE_URL is required when TELEGRAM_MODE=webhook.")
        webhook_url = (
            settings.telegram_public_base_url.rstrip("/") + settings.telegram_webhook_path
        )
        await api.set_webhook(webhook_url, settings.telegram_webhook_secret)
        logger.info(
            "telegram_delivery_configured",
            extra={
                "event": "telegram_delivery_configured",
                "mode": "telegram_webhook",
            },
        )
        return

    await api.delete_webhook()
    logger.info(
        "telegram_delivery_configured",
        extra={
            "event": "telegram_delivery_configured",
            "mode": "telegram_polling",
        },
    )


async def main() -> None:
    """CLI entrypoint for the Telegram polling bot."""
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the Telegram adapter.")

    services = build_runtime_services()
    api = TelegramBotAPI(settings.telegram_bot_token)
    await configure_telegram_delivery(api)
    runner = TelegramBotRunner(api=api, services=services)
    await runner.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
