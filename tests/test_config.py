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
