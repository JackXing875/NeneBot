import json

from starlette.requests import Request

from src.core.auth import (
    configured_auth_identities,
    extract_api_token,
    require_api_auth,
    require_api_scope,
    token_subject,
    validate_api_token,
)
from src.core.config import settings
from src.core.exceptions import AuthenticationError, AuthorizationError


def make_request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
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


def test_extract_api_token_supports_bearer_header(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_header_name", "Authorization")
    request = make_request([(b"authorization", b"Bearer secret-token")])

    assert extract_api_token(request) == "secret-token"


def test_validate_api_token_matches_configured_values(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_tokens", "service-a|chat:alpha,beta")

    matched = validate_api_token("beta")
    assert matched is not None
    assert matched.name == "token-2"
    assert matched.token == "beta"
    assert matched.scopes == {"chat", "ops"}
    assert validate_api_token("missing") is None


def test_configured_auth_identities_support_named_tokens(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_tokens", "ci-bot|chat:alpha,ops|ops:beta,gamma")
    monkeypatch.setattr(settings, "api_auth_registry_path", "/tmp/does-not-exist.json")

    identities = configured_auth_identities()

    assert [item.name for item in identities] == ["ci-bot", "ops", "token-3"]
    assert [item.token for item in identities] == ["alpha", "beta", "gamma"]
    assert identities[0].scopes == {"chat"}
    assert identities[1].scopes == {"ops"}
    assert identities[2].scopes == {"chat", "ops"}


def test_configured_auth_identities_support_registry_file(monkeypatch, tmp_path) -> None:
    registry_path = tmp_path / "api_tokens.json"
    registry_path.write_text(
        json.dumps(
            [
                {"name": "dashboard", "token": "ops-secret", "scopes": ["ops"]},
                {"name": "frontend", "token": "chat-secret", "scopes": ["chat"]},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "api_auth_tokens", "")
    monkeypatch.setattr(settings, "api_auth_registry_path", str(registry_path))

    identities = configured_auth_identities()

    assert [item.name for item in identities] == ["dashboard", "frontend"]
    assert identities[0].scopes == {"ops"}
    assert identities[1].scopes == {"chat"}


def test_require_api_auth_rejects_missing_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_auth_tokens", "secret-token")
    monkeypatch.setattr(settings, "api_auth_registry_path", "/tmp/does-not-exist.json")

    request = make_request()

    try:
        require_api_auth(request)
    except AuthenticationError as exc:
        assert exc.code == "auth_required"
        assert exc.status_code == 401
    else:
        raise AssertionError("AuthenticationError was not raised")


def test_require_api_auth_sets_audit_subject(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_auth_tokens", "ci-bot|chat:secret-token")
    monkeypatch.setattr(settings, "api_auth_registry_path", "/tmp/does-not-exist.json")
    request = make_request([(b"authorization", b"Bearer secret-token")])

    require_api_auth(request)

    assert request.state.auth_subject == "ci-bot"
    assert request.state.auth_token_preview == token_subject("secret-token")
    assert request.state.auth_scopes == ["chat"]


def test_require_api_scope_rejects_missing_scope(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_auth_tokens", "ci-bot|chat:secret-token")
    monkeypatch.setattr(settings, "api_auth_registry_path", "/tmp/does-not-exist.json")
    request = make_request([(b"authorization", b"Bearer secret-token")])

    try:
        require_api_scope("ops")(request)
    except AuthorizationError as exc:
        assert exc.code == "forbidden"
        assert exc.status_code == 403
    else:
        raise AssertionError("AuthorizationError was not raised")
