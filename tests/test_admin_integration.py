from starlette.requests import Request

from src.core.auth import require_api_scope
from src.core.config import settings
from src.core.exceptions import AuthenticationError, AuthorizationError


def make_request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/admin/api/overview",
        "headers": headers or [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "server": ("testserver", 80),
        "root_path": "",
        "http_version": "1.1",
        "state": {},
    }
    return Request(scope)


def test_admin_ops_scope_rejects_missing_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_auth_tokens", "ops-dashboard|ops:secret-token")
    monkeypatch.setattr(settings, "api_auth_registry_path", "/tmp/does-not-exist.json")

    request = make_request()

    try:
        require_api_scope("ops")(request)
    except AuthenticationError as exc:
        assert exc.code == "auth_required"
        assert exc.status_code == 401
    else:
        raise AssertionError("AuthenticationError was not raised")


def test_admin_ops_scope_rejects_chat_only_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_auth_tokens", "frontend|chat:chat-token")
    monkeypatch.setattr(settings, "api_auth_registry_path", "/tmp/does-not-exist.json")

    request = make_request([(b"authorization", b"Bearer chat-token")])

    try:
        require_api_scope("ops")(request)
    except AuthorizationError as exc:
        assert exc.code == "forbidden"
        assert exc.status_code == 403
    else:
        raise AssertionError("AuthorizationError was not raised")
