"""Tests for the Hindsight memory adapter using a mocked SDK client."""

from datetime import datetime, timezone
from typing import cast
from unittest.mock import Mock

import pytest
from hindsight_client import Hindsight
from hindsight_client_api.exceptions import ApiException

from backend.memory.hindsight_client import (
    HindsightConfigurationError,
    HindsightMemoryClient,
    HindsightMemoryClientError,
)


def make_sdk_client() -> Mock:
    return Mock(spec=Hindsight)


def test_client_uses_hindsight_environment_settings(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_BASE_URL", "https://memory.example.test")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "test-token")
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "deal-intelligence")
    sdk_constructor = Mock(return_value=make_sdk_client())
    monkeypatch.setattr("backend.memory.hindsight_client.Hindsight", sdk_constructor)

    HindsightMemoryClient()

    sdk_constructor.assert_called_once_with(
        base_url="https://memory.example.test",
        api_key="test-token",
    )


def test_client_rejects_empty_base_url(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_BASE_URL", " ")

    with pytest.raises(HindsightConfigurationError, match="HINDSIGHT_BASE_URL"):
        HindsightMemoryClient()


def test_retain_memory_forwards_supported_options(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "dealmind")
    sdk = make_sdk_client()
    response = Mock()
    sdk.retain.return_value = response
    client = HindsightMemoryClient(sdk_client=cast(Hindsight, sdk))
    timestamp = datetime(2026, 9, 28, tzinfo=timezone.utc)

    result = client.retain_memory(
        "The buyer needs SSO before procurement approval.",
        timestamp=timestamp,
        context="discovery call",
        document_id="call-42",
        metadata={"deal_id": "deal-42"},
        tags=["objection", "security"],
    )

    assert result is response
    sdk.retain.assert_called_once_with(
        bank_id="dealmind",
        content="The buyer needs SSO before procurement approval.",
        timestamp=timestamp,
        context="discovery call",
        document_id="call-42",
        metadata={"deal_id": "deal-42"},
        tags=["objection", "security"],
    )


def test_recall_memory_forwards_query_and_filters():
    sdk = make_sdk_client()
    response = Mock()
    sdk.recall.return_value = response
    client = HindsightMemoryClient(sdk_client=cast(Hindsight, sdk))

    result = client.recall_memory(
        "What concerns remain on this deal?",
        bank_id="deal-42",
        types=["world", "observation"],
        tags=["deal-42"],
        include_chunks=True,
    )

    assert result is response
    sdk.recall.assert_called_once_with(
        bank_id="deal-42",
        query="What concerns remain on this deal?",
        max_tokens=4096,
        budget="mid",
        include_chunks=True,
        types=["world", "observation"],
        tags=["deal-42"],
    )


def test_reflect_memory_requests_supporting_facts():
    sdk = make_sdk_client()
    response = Mock()
    sdk.reflect.return_value = response
    client = HindsightMemoryClient(sdk_client=cast(Hindsight, sdk))

    result = client.reflect_memory(
        "What should the rep do next?",
        bank_id="deal-42",
        context="before the renewal meeting",
    )

    assert result is response
    sdk.reflect.assert_called_once_with(
        bank_id="deal-42",
        query="What should the rep do next?",
        budget="low",
        include_facts=True,
        context="before the renewal meeting",
    )


def test_sdk_api_errors_are_wrapped_with_operation_context():
    sdk = make_sdk_client()
    api_error = ApiException(status=503, reason="Unavailable")
    sdk.recall.side_effect = api_error
    client = HindsightMemoryClient(sdk_client=cast(Hindsight, sdk))

    with pytest.raises(
           HindsightMemoryClientError,
           match=r"Hindsight recall request failed \(HTTP 503\)",
    ) as error:
        client.recall_memory("Find the latest pricing discussion.")

    assert error.value.__cause__ is api_error