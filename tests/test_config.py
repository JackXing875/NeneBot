from src.core.config import Settings


def test_settings_load_session_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.session_backend == "memory"
    assert settings.redis_url == "redis://127.0.0.1:6379/0"
    assert settings.session_ttl_seconds == 86400
