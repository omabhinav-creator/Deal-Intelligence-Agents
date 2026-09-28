"""Mocked tests for structured sales intelligence extraction."""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
from groq import Groq

from Hindsight.ai.extraction import (
	ExtractionConfigurationError,
	ExtractionError,
	ExtractedFact,
	ExtractedStakeholder,
	SalesIntelligenceExtraction,
	SalesIntelligenceExtractor,
)
from Hindsight.memory.memory_schema import MemoryType


def make_groq_client(content: str) -> tuple[Groq, Mock]:
	client = Mock()
	message = SimpleNamespace(content=content, refusal=None)
	client.chat.completions.create.return_value = SimpleNamespace(
		choices=[SimpleNamespace(message=message)]
	)
	return cast(Groq, client), client


def example_extraction() -> SalesIntelligenceExtraction:
	return SalesIntelligenceExtraction(
		customer_company="TechNova",
		stakeholders=[
			ExtractedStakeholder(name="CTO", role="CTO"),
			ExtractedStakeholder(name="Sarah", role="procurement"),
		],
		stakeholder_concerns=[
			ExtractedFact(
				content="Concerned about integration with the existing ERP.",
				stakeholder_name="CTO",
			)
		],
		objections=[
			ExtractedFact(
				content="Worried about integration with the existing ERP.",
				stakeholder_name="CTO",
			)
		],
		competitors=[ExtractedFact(content="Comparing the product with CompetitorX.")],
		pricing_information=[
			ExtractedFact(
				content="Asked whether the annual price could be reduced.",
				stakeholder_name="Sarah",
			)
		],
		customer_requests=[
			ExtractedFact(
				content="Asked whether the annual price could be reduced.",
				stakeholder_name="Sarah",
			)
		],
	)


def test_extractor_uses_groq_json_schema_and_returns_validated_data():
	expected = example_extraction()
	client, mock = make_groq_client(expected.model_dump_json())
	extractor = SalesIntelligenceExtractor(client=client, model="test-model")
	notes = (
		"TechNova's CTO likes the product but is worried about integration with "
		"their existing ERP. Sarah from procurement also asked whether we can "
		"reduce the annual price. They are comparing us with CompetitorX."
	)

	result = extractor.extract(notes)

	assert result == expected
	call = mock.chat.completions.create.call_args.kwargs
	assert call["model"] == "test-model"
	assert call["messages"][1]["content"] == notes
	assert call["response_format"]["type"] == "json_schema"
	assert call["response_format"]["json_schema"]["strict"] is False
	assert (
		call["response_format"]["json_schema"]["schema"]
		== SalesIntelligenceExtraction.model_json_schema()
	)


def test_extracted_facts_convert_to_deal_memories_for_the_retain_workflow():
	extraction = example_extraction()
	interaction_date = datetime(2026, 9, 28, tzinfo=timezone.utc)

	memories = extraction.to_deal_memories(
		deal_id="deal-7",
		interaction_date=interaction_date,
		interaction_id="meeting-7",
		interaction_source="sales meeting",
	)

	assert len(memories) == 7
	assert all(memory.deal_id == "deal-7" for memory in memories)
	assert all(memory.customer_name == "TechNova" for memory in memories)
	assert all(memory.interaction_date == interaction_date for memory in memories)
	assert {memory.memory_type for memory in memories} == {
		MemoryType.STAKEHOLDER,
		MemoryType.STAKEHOLDER_CONCERN,
		MemoryType.OBJECTION,
		MemoryType.COMPETITOR,
		MemoryType.PRICING_DISCUSSION,
		MemoryType.CUSTOMER_REQUEST,
	}
	assert any(
		"TechNova" in memory.content and "CTO" in memory.content
		for memory in memories
		if memory.memory_type == MemoryType.STAKEHOLDER_CONCERN
	)
	assert any("CompetitorX" in memory.content for memory in memories)


def test_unknown_fields_default_to_empty_and_missing_deal_id_is_safe():
	client, _ = make_groq_client('{"customer_company":"TechNova"}')
	result = SalesIntelligenceExtractor(client=client).extract("TechNova meeting notes")

	assert result.deal_id is None
	assert result.stakeholders == []
	assert result.objections == []
	with pytest.raises(ValueError, match="deal_id is required"):
		result.to_deal_memories()


def test_extractor_requires_groq_key_when_not_given_a_mocked_client(monkeypatch):
	monkeypatch.setattr(
		"Hindsight.ai.extraction.get_settings",
		lambda: SimpleNamespace(groq_api_key=None, groq_model="test-model"),
	)

	with pytest.raises(ExtractionConfigurationError, match="GROQ_API_KEY is required"):
		SalesIntelligenceExtractor()


def test_empty_notes_are_rejected_without_calling_groq():
	client, mock = make_groq_client("{}")
	extractor = SalesIntelligenceExtractor(client=client)

	with pytest.raises(ValueError, match="meeting_notes must not be empty"):
		extractor.extract("  ")
	mock.chat.completions.create.assert_not_called()


def test_invalid_groq_json_is_reported_as_extraction_error():
	client, _ = make_groq_client("not-json")
	extractor = SalesIntelligenceExtractor(client=client)

	with pytest.raises(ExtractionError, match="did not match the extraction schema"):
		extractor.extract("A fictional sales meeting.")