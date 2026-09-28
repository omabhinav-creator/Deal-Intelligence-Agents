"""Tests for the mocked meeting-note to Hindsight interaction workflow."""

from datetime import datetime, timezone
from typing import cast
from unittest.mock import Mock

import pytest
from groq import Groq
from hindsight_client import Hindsight
from hindsight_client_api.models.retain_response import RetainResponse

from backend.memory.hindsight_client import (
	HindsightMemoryClient,
	HindsightMemoryClientError,
)
from Hindsight.ai.agent import (
	InteractionProcessingError,
	process_sales_interaction,
)
from Hindsight.ai.extraction import (
	ExtractionError,
	ExtractedFact,
	ExtractedStakeholder,
	SalesIntelligenceExtraction,
	SalesIntelligenceExtractor,
)
from Hindsight.memory.memory_schema import MemoryType


def mock_extractor(
	extraction: SalesIntelligenceExtraction | None = None,
) -> Mock:
	extractor = Mock(spec=SalesIntelligenceExtractor)
	extractor.extract.return_value = extraction or SalesIntelligenceExtraction(
		customer_company="TechNova",
		stakeholders=[
			ExtractedStakeholder(name="CTO", role="CTO"),
			ExtractedStakeholder(name="Sarah", role="procurement"),
		],
		stakeholder_concerns=[
			ExtractedFact(
				content="Concerned about ERP integration.",
				stakeholder_name="CTO",
			)
		],
		competitors=[ExtractedFact(content="Evaluating CompetitorX.")],
		pricing_information=[
			ExtractedFact(
				content="Asked whether the annual price can be reduced.",
				stakeholder_name="Sarah",
			)
		],
		customer_requests=[
			ExtractedFact(
				content="Asked whether the annual price can be reduced.",
				stakeholder_name="Sarah",
			)
		],
	)
	return extractor


def mock_memory_client() -> Mock:
	client = Mock(spec=HindsightMemoryClient)
	client.retain_memory.return_value = Mock(spec=RetainResponse)
	return client


def test_process_sales_interaction_runs_notes_to_hindsight_retain():
	meeting_notes = (
		"The CTO likes the product but is concerned about ERP integration. "
		"Sarah from procurement asked whether the annual price can be reduced. "
		"They are also evaluating CompetitorX."
	)
	interaction_date = datetime(2026, 9, 28, tzinfo=timezone.utc)
	extractor = mock_extractor()
	memory_client = mock_memory_client()

	result = process_sales_interaction(
		deal_id="technova-discovery-1",
		customer_company="TechNova",
		interaction_date=interaction_date,
		interaction_id="technova-discovery-meeting",
		interaction_source="discovery_meeting",
		meeting_notes=meeting_notes,
		extractor=cast(SalesIntelligenceExtractor, extractor),
		memory_client=cast(HindsightMemoryClient, memory_client),
	)

	extractor.extract.assert_called_once_with(meeting_notes)
	assert result.extraction.customer_company == "TechNova"
	assert len(result.memories) == 6
	assert len(result.retain_responses) == 6
	assert memory_client.retain_memory.call_count == 6
	retained_contents = [
		call.args[0] for call in memory_client.retain_memory.call_args_list
	]
	assert any("ERP integration" in content and "CTO" in content for content in retained_contents)
	assert any("CompetitorX" in content for content in retained_contents)
	assert any("annual price" in content and "Sarah" in content for content in retained_contents)
	for call in memory_client.retain_memory.call_args_list:
		assert call.kwargs["metadata"]["deal_id"] == "technova-discovery-1"
		assert call.kwargs["metadata"]["customer_name"] == "TechNova"
		assert call.kwargs["metadata"]["interaction_date"] == interaction_date.isoformat()
		assert call.kwargs["metadata"]["memory_type"]
		assert call.kwargs["metadata"]["interaction_source"] == "discovery_meeting"


def test_empty_meeting_notes_fail_before_extraction_or_hindsight():
	extractor = mock_extractor()
	memory_client = mock_memory_client()

	with pytest.raises(ValueError, match="meeting_notes must not be empty"):
		process_sales_interaction(
			deal_id="deal-1",
			meeting_notes="  ",
			extractor=cast(SalesIntelligenceExtractor, extractor),
			memory_client=cast(HindsightMemoryClient, memory_client),
		)

	extractor.extract.assert_not_called()
	memory_client.retain_memory.assert_not_called()


def test_extraction_failure_is_reported_without_hindsight_calls():
	extractor = mock_extractor()
	extractor.extract.side_effect = ExtractionError("mock extraction failure")
	memory_client = mock_memory_client()

	with pytest.raises(InteractionProcessingError, match="extraction failed"):
		process_sales_interaction(
			deal_id="deal-1",
			meeting_notes="A fictional meeting.",
			extractor=cast(SalesIntelligenceExtractor, extractor),
			memory_client=cast(HindsightMemoryClient, memory_client),
		)

	memory_client.retain_memory.assert_not_called()


def test_hindsight_failure_reports_partial_retains():
	extractor = mock_extractor()
	memory_client = mock_memory_client()
	memory_client.retain_memory.side_effect = [
		Mock(spec=RetainResponse),
		HindsightMemoryClientError("mock retain failure"),
	]

	with pytest.raises(InteractionProcessingError, match="after 1 of 6 memories"):
		process_sales_interaction(
			deal_id="deal-1",
			meeting_notes="A fictional meeting.",
		extractor=cast(SalesIntelligenceExtractor, extractor),
			memory_client=cast(HindsightMemoryClient, memory_client),
		)