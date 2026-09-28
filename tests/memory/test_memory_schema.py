"""Tests for DealMind's Hindsight-oriented memory schema."""

from datetime import datetime, timezone
from typing import cast
from unittest.mock import Mock

import pytest
from hindsight_client_api.models.retain_response import RetainResponse
from pydantic import ValidationError

from backend.memory.hindsight_client import HindsightMemoryClient
from Hindsight.memory.memory_schema import DealMemory, MemoryType
from Hindsight.memory.retain import retain_deal_memory


def test_memory_type_covers_the_deal_intelligence_categories():
    assert {memory_type.value for memory_type in MemoryType} == {
        "deal",
        "customer",
        "customer_requirement",
        "interaction",
        "objection",
        "stakeholder",
		"stakeholder_concern",
        "competitor",
        "pricing_discussion",
        "customer_request",
        "commitment",
        "sales_action",
        "important_fact",
        "risk",
        "buying_signal",
        "unresolved_question",
        "deal_outcome",
        "lesson_learned",
    }


def test_deal_memory_requires_deal_id_content_and_known_type():
    with pytest.raises(ValidationError):
        DealMemory(memory_type=MemoryType.OBJECTION, content="Needs SSO")

    with pytest.raises(ValidationError):
        DealMemory(deal_id="deal-1", memory_type=MemoryType.OBJECTION, content=" ")

    with pytest.raises(ValidationError):
        DealMemory(deal_id="deal-1", memory_type="unknown", content="A fact")


def test_deal_memory_builds_hindsight_metadata_and_tags():
    interaction_date = datetime(2026, 9, 28, 12, 30, tzinfo=timezone.utc)
    memory = DealMemory(
        deal_id="deal-1",
        memory_type=MemoryType.OBJECTION,
        content="TechNova's CTO is concerned about API integration.",
        customer_name="TechNova",
        interaction_id="meeting-3",
        interaction_date=interaction_date,
        interaction_source="discovery meeting",
        stakeholder_name="CTO",
        status="open",
    )

    assert memory.to_hindsight_metadata() == {
        "deal_id": "deal-1",
        "memory_type": "objection",
        "customer_name": "TechNova",
        "interaction_id": "meeting-3",
        "interaction_date": "2026-09-28T12:30:00+00:00",
        "interaction_source": "discovery meeting",
        "stakeholder_name": "CTO",
        "status": "open",
    }
    assert memory.to_hindsight_tags() == ["deal:deal-1", "type:objection"]


def test_retain_deal_memory_uses_the_existing_hindsight_wrapper():
    response = Mock(spec=RetainResponse)
    client = Mock(spec=HindsightMemoryClient)
    client.retain_memory.return_value = response
    memory = DealMemory(
        deal_id="deal-2",
        memory_type=MemoryType.COMMITMENT,
        content="Sales will send the security questionnaire by Friday.",
        interaction_id="meeting-8",
        interaction_source="customer meeting",
    )

    result = retain_deal_memory(memory, cast(HindsightMemoryClient, client))

    assert result is response
    client.retain_memory.assert_called_once_with(
        memory.content,
        timestamp=None,
        context="customer meeting",
        document_id="meeting-8",
        metadata={
            "deal_id": "deal-2",
            "memory_type": "commitment",
            "interaction_id": "meeting-8",
            "interaction_source": "customer meeting",
        },
        tags=["deal:deal-2", "type:commitment"],
    )