r"""Opt-in live test for TechNova memory retain and recall.

Run with ``$env:HINDSIGHT_E2E='1'; .\.venv\Scripts\python.exe -m pytest -v tests/memory/test_hindsight_e2e.py``.
"""

import os
from uuid import uuid4
from urllib.parse import urlsplit

import pytest
from hindsight_client import Hindsight

from backend.memory.hindsight_client import (
    HindsightMemoryClient,
    HindsightMemoryClientError,
)
from Hindsight.config import get_settings


@pytest.fixture
def technova_test_bank_id():
    if os.getenv("HINDSIGHT_E2E") != "1":
        pytest.skip("Set HINDSIGHT_E2E=1 to run against a live Hindsight API.")

    settings = get_settings()
    parsed_base_url = urlsplit(settings.hindsight_base_url)
    if parsed_base_url.scheme not in {"http", "https"} or not parsed_base_url.netloc:
        pytest.fail(
            "HINDSIGHT_BASE_URL must be an absolute http(s) API URL. "
            "Remove any variable-name text from its value.",
            pytrace=False,
        )

    bank_id = f"dealmind-e2e-technova-{uuid4().hex[:12]}"
    sdk_client = Hindsight(
        base_url=settings.hindsight_base_url,
        api_key=settings.hindsight_api_key,
    )
    bank_created = False
    try:
        try:
            sdk_client.create_bank(
                bank_id=bank_id,
                name="DealMind fictional TechNova E2E test",
            )
            bank_created = True
        except Exception as exc:
            pytest.fail(
                "Could not create the temporary Hindsight test bank "
                f"({type(exc).__name__}). Check the URL, credentials, and server. ",
                pytrace=False,
            )
        yield bank_id
    finally:
        if bank_created:
            try:
                sdk_client.delete_bank(bank_id)
            except Exception as exc:
                pytest.fail(
                    "Could not delete the temporary Hindsight test bank "
                    f"({type(exc).__name__}).",
                    pytrace=False,
                )
        sdk_client.close()


def test_technova_memories_can_be_recalled(technova_test_bank_id: str) -> None:
    client = HindsightMemoryClient()
    memories = (
        "TechNova's CTO is concerned about API integration.",
        "TechNova is comparing our product with Salesforce.",
        "TechNova thinks our pricing is too high.",
    )
    tags = ["technova-e2e"]

    try:
        for index, content in enumerate(memories, start=1):
            client.retain_memory(
                content,
                bank_id=technova_test_bank_id,
                document_id=f"technova-e2e-interaction-{index}",
                tags=tags,
            )

        response = client.recall_memory(
            "What are TechNova's main concerns, competitors and pricing issues?",
            bank_id=technova_test_bank_id,
            tags=tags,
            max_tokens=4096,
        )
    except HindsightMemoryClientError as exc:
        pytest.fail(f"TechNova Hindsight retain/recall failed: {exc}", pytrace=False)
    finally:
        client.close()

    recalled_text = " ".join(result.text for result in response.results).casefold()

    assert "technova" in recalled_text
    assert "integration" in recalled_text or "api" in recalled_text
    assert "salesforce" in recalled_text
    assert "pricing" in recalled_text or "price" in recalled_text