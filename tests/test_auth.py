from starlette.requests import Request

from src.core.auth import extract_api_token, require_api_auth, token_subject, validate_api_token
from src.core.config import settings
from src.core.exceptions import AuthenticationError


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
    monkeypatch.setattr(settings, "api_auth_tokens", "alpha,beta")

    assert validate_api_token("beta") == "beta"
    assert validate_api_token("missing") is None


def test_require_api_auth_rejects_missing_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_auth_tokens", "secret-token")

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
    monkeypatch.setattr(settings, "api_auth_tokens", "secret-token")
    request = make_request([(b"authorization", b"Bearer secret-token")])

    require_api_auth(request)

    assert request.state.auth_subject == token_subject("secret-token")
