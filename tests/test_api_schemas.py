import pytest
from pydantic import ValidationError

from src.api.schemas import MAX_QUERY_LENGTH, ChatRequest

SESSION_ID = "123e4567-e89b-42d3-a456-426614174000"


def test_chat_request_trims_query_and_accepts_safe_session_id() -> None:
    request = ChatRequest(query="  你好\n", session_id=SESSION_ID)

    assert request.query == "你好"
    assert request.session_id == SESSION_ID


@pytest.mark.parametrize("query", ["", " ", "\n\t"])
def test_chat_request_rejects_blank_query(query: str) -> None:
    with pytest.raises(ValidationError):
        ChatRequest(query=query)


def test_chat_request_rejects_oversized_query() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(query="x" * (MAX_QUERY_LENGTH + 1))


@pytest.mark.parametrize(
    "session_id",
    [
        "contains spaces",
        "../escape",
        "中文会话",
        "client-session_01",
        "123e4567-e89b-12d3-a456-426614174000",
        "123E4567-E89B-42D3-A456-426614174000",
        "telegram:123456",
        "Telegram:-100123456",
        "x" * 129,
    ],
)
def test_chat_request_rejects_unsafe_or_reserved_session_id(session_id: str) -> None:
    with pytest.raises(ValidationError):
        ChatRequest(query="hello", session_id=session_id)
