from src.core.config import Settings


def test_settings_load_session_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.session_backend == "memory"
    assert settings.redis_url == "redis://127.0.0.1:6379/0"
    assert settings.session_ttl_seconds == 86400


def test_settings_model_config_uses_env_file_defaults() -> None:
    assert Settings.model_config["env_file"] == ".env"
    assert Settings.model_config["env_file_encoding"] == "utf-8"
