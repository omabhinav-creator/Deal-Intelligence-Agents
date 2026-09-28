"""Tests for loading DealMind environment settings."""

from Hindsight.config import get_settings


def test_get_settings_uses_defaults_when_variables_are_missing(monkeypatch):
    variables = (
        "HINDSIGHT_BASE_URL",
        "HINDSIGHT_API_KEY",
        "HINDSIGHT_BANK_ID",
        "GROQ_API_KEY",
        "GROQ_MODEL",
    )
    for variable in variables:
        monkeypatch.delenv(variable, raising=False)

    settings = get_settings()

    assert settings.hindsight_base_url == "http://localhost:8888"
    assert settings.hindsight_api_key is None
    assert settings.hindsight_bank_id == "dealmind"
    assert settings.groq_api_key is None
    assert settings.groq_model == "openai/gpt-oss-20b"


def test_get_settings_reads_environment_variables(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_BASE_URL", "https://memory.example.test")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "hindsight-placeholder")
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "deal-123")
    monkeypatch.setenv("GROQ_API_KEY", "groq-placeholder")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")

    settings = get_settings()

    assert settings.hindsight_base_url == "https://memory.example.test"
    assert settings.hindsight_api_key == "hindsight-placeholder"
    assert settings.hindsight_bank_id == "deal-123"
    assert settings.groq_api_key == "groq-placeholder"
    assert settings.groq_model == "openai/gpt-oss-20b"