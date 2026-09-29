"""Tests for loading DealMind environment settings."""

from Hindsight.config import get_settings


def test_get_settings_uses_defaults_when_variables_are_missing(monkeypatch):
    variables = (
        "HINDSIGHT_BASE_URL",
        "HINDSIGHT_API_KEY",
        "HINDSIGHT_BANK_ID",
        "GROQ_API_KEY_AI",
        "GROQ_API_KEY_BACKEND",
        "MONGO_URI",
        "DATABASE_NAME",
        "GROQ_MODEL",
    )
    for variable in variables:
        monkeypatch.delenv(variable, raising=False)

    settings = get_settings()

    assert settings.hindsight_base_url == "http://localhost:8888"
    assert settings.hindsight_api_key is None
    assert settings.hindsight_bank_id == "dealmind"
    assert settings.ai_groq_api_key is None
    assert settings.backend_groq_api_key is None
    assert settings.mongo_uri is None
    assert settings.database_name == "dealmind"
    assert settings.groq_model == "openai/gpt-oss-20b"


def test_get_settings_reads_environment_variables(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_BASE_URL", "https://memory.example.test")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "hindsight-placeholder")
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "deal-123")
    monkeypatch.setenv("GROQ_API_KEY_AI", "ai-groq-placeholder")
    monkeypatch.setenv("GROQ_API_KEY_BACKEND", "backend-groq-placeholder")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("DATABASE_NAME", "test-dealmind")

    settings = get_settings()

    assert settings.hindsight_base_url == "https://memory.example.test"
    assert settings.hindsight_api_key == "hindsight-placeholder"
    assert settings.hindsight_bank_id == "deal-123"
    assert settings.ai_groq_api_key == "ai-groq-placeholder"
    assert settings.backend_groq_api_key == "backend-groq-placeholder"
    assert settings.mongo_uri == "mongodb://localhost:27017"
    assert settings.database_name == "test-dealmind"
    assert settings.groq_model == "openai/gpt-oss-20b"
