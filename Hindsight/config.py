"""Load DealMind service configuration without exposing credentials."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
# The repository's original MongoDB service keeps its local configuration here.
# Existing process environment values always take precedence over either file.
load_dotenv(PROJECT_ROOT / "backend" / ".env")


@dataclass(frozen=True)
class Settings:
	"""Configuration shared by the API, Hindsight services, and MongoDB layer."""

	hindsight_base_url: str
	hindsight_api_key: str | None
	hindsight_bank_id: str
	ai_groq_api_key: str | None
	backend_groq_api_key: str | None
	groq_model: str
	mongo_uri: str | None
	database_name: str
	auth_session_ttl_hours: int


def get_settings() -> Settings:
    """Return settings, leaving credentials unset until the user provides them."""
    return Settings(
        hindsight_base_url=os.getenv(
            "HINDSIGHT_BASE_URL", "http://localhost:8888"
        ),
        hindsight_api_key=os.getenv("HINDSIGHT_API_KEY") or None,
        hindsight_bank_id=os.getenv("HINDSIGHT_BANK_ID", "dealmind"),
		ai_groq_api_key=os.getenv("GROQ_API_KEY_AI") or None,
		backend_groq_api_key=os.getenv("GROQ_API_KEY_BACKEND") or None,
		groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
		mongo_uri=os.getenv("MONGO_URI") or None,
		database_name=os.getenv("DATABASE_NAME", "dealmind"),
		auth_session_ttl_hours=int(os.getenv("AUTH_SESSION_TTL_HOURS", "168")),
	)
