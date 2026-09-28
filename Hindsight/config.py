"""Load local Hindsight and LLM settings from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    hindsight_base_url: str
    hindsight_api_key: str | None
    hindsight_bank_id: str
    groq_api_key: str | None
    groq_model: str


def get_settings() -> Settings:
    """Return settings, leaving credentials unset until the user provides them."""
    return Settings(
        hindsight_base_url=os.getenv(
            "HINDSIGHT_BASE_URL", "http://localhost:8888"
        ),
        hindsight_api_key=os.getenv("HINDSIGHT_API_KEY") or None,
        hindsight_bank_id=os.getenv("HINDSIGHT_BANK_ID", "dealmind"),
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
    )