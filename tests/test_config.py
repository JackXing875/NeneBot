import pytest
from pydantic import ValidationError

from src.core.config import Settings, resolve_env_files


def test_settings_load_session_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.session_backend == "memory"
    assert settings.redis_url == "redis://127.0.0.1:6379/0"
    assert settings.session_ttl_seconds == 86400


def test_settings_model_config_uses_env_file_defaults() -> None:
    assert Settings.model_config["env_file"] == (".env", ".env.dev")
    assert Settings.model_config["env_file_encoding"] == "utf-8"


def test_resolve_env_files_defaults_to_dev(monkeypatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    assert resolve_env_files() == (".env", ".env.dev")


def test_resolve_env_files_uses_selected_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    assert resolve_env_files() == (".env", ".env.prod")


def test_settings_allow_data_path_override(monkeypatch) -> None:
    monkeypatch.setenv("DATA_PATH", "/tmp/custom-train.jsonl")

    settings = Settings(_env_file=None)

    assert settings.data_path == "/tmp/custom-train.jsonl"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("port", 0),
        ("match_threshold", 1.1),
        ("session_max_history", 1),
        ("session_ttl_seconds", 0),
        ("api_rate_limit_count", 0),
        ("llm_timeout_seconds", -1),
        ("llm_max_retries", 11),
    ],
)
def test_settings_reject_unsafe_numeric_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


@pytest.mark.parametrize("redis_url", ["", "http://localhost:6379", "redis:///0"])
def test_settings_reject_invalid_redis_url(redis_url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, redis_url=redis_url)


def test_settings_require_redis_in_production() -> None:
    with pytest.raises(ValidationError, match="SESSION_BACKEND=redis"):
        Settings(_env_file=None, app_env="prod", session_backend="memory")


def test_settings_accept_secure_redis_configuration_in_production() -> None:
    settings = Settings(
        _env_file=None,
        app_env="PROD",
        session_backend="REDIS",
        redis_url="rediss://redis.example.test:6380/0",
    )

    assert settings.app_env == "prod"
    assert settings.session_backend == "redis"
