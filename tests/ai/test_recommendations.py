"""Mocked evidence-backed recommendation explanation tests for TechNova."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
from groq import Groq

from backend.memory.hindsight_client import HindsightMemoryClient
from Hindsight.ai.deal_brief import BriefEvidence
from Hindsight.ai.recommendations import (
	RecommendationError,
	RecommendationExplainer,
	RecommendationWhyDraft,
)


def memory(
	memory_id: str,
	content: str,
	*,
	deal_id: str = "technova-deal",
	date: str = "2026-09-28T12:00:00Z",
	source: str = "discovery meeting",
) -> SimpleNamespace:
	return SimpleNamespace(
		id=memory_id,
		text=content,
		type="world",
		metadata={
			"deal_id": deal_id,
			"memory_type": "stakeholder_concern",
			"customer_name": "TechNova",
			"interaction_date": date,
			"interaction_source": source,
		},
		tags=[f"deal:{deal_id}"],
		occurred_start=date,
		mentioned_at=None,
	)


def make_groq_client(
	draft: RecommendationWhyDraft,
) -> tuple[Groq, Mock]:
	client = Mock()
	message = SimpleNamespace(content=draft.model_dump_json(), refusal=None)
	client.chat.completions.create.return_value = SimpleNamespace(
		choices=[SimpleNamespace(message=message)]
	)
	return cast(Groq, client), client


def make_explainer(
	memories: list[SimpleNamespace],
	draft: RecommendationWhyDraft,
) -> tuple[RecommendationExplainer, Mock, Mock]:
	memory_client = Mock(spec=HindsightMemoryClient)
	memory_client.recall_memory.return_value = SimpleNamespace(results=memories)
	groq_client, groq_mock = make_groq_client(draft)
	explainer = RecommendationExplainer(
		memory_client=cast(HindsightMemoryClient, memory_client),
		groq_client=groq_client,
		model="mock-model",
	)
	return explainer, memory_client, groq_mock


def test_strong_evidence_returns_reason_and_source_metadata():
	source = memory(
		"memory-1",
		"TechNova's CTO raised the ERP integration concern for the second time.",
		source="discovery meeting",
	)
	draft = RecommendationWhyDraft(
		reason="The CTO has raised ERP integration concerns repeatedly.",
		supporting_memory_ids=["memory-1"],
	)
	explainer, memory_client, _ = make_explainer([source], draft)

	result = explainer.explain(
		"technova-deal",
		"Prepare ERP integration documentation before the next CTO meeting.",
	)

	assert result.insufficient_evidence is False
	assert result.reason == draft.reason
	assert result.recommended_action.startswith("Prepare ERP")
	assert result.supporting_memories == [
		BriefEvidence(
			memory_id="memory-1",
			content=source.text,
			memory_type="stakeholder_concern",
			customer_company="TechNova",
			interaction_date="2026-09-28T12:00:00Z",
			interaction_source="discovery meeting",
		)
	]
	recall_args = memory_client.recall_memory.call_args
	assert recall_args.kwargs["tags"] == ["deal:technova-deal"]
	assert "technova-deal" in recall_args.args[0]


def test_multiple_memories_are_preserved_as_separate_evidence():
	memories = [
		memory("concern-1", "TechNova's CTO raised ERP integration."),
		memory("concern-2", "The CTO again asked about ERP integration."),
	]
	draft = RecommendationWhyDraft(
		reason="The same integration issue has come up in two meetings.",
		supporting_memory_ids=["concern-1", "concern-2"],
	)
	explainer, _, _ = make_explainer(memories, draft)

	result = explainer.explain("technova-deal", "Prepare integration details.")

	assert [item.memory_id for item in result.supporting_memories] == [
		"concern-1",
		"concern-2",
	]


def test_insufficient_evidence_is_explicit_and_cites_any_limited_source():
	source = memory("weak-1", "TechNova had a routine product check-in.")
	draft = RecommendationWhyDraft(
		reason="The available note does not address this proposed pricing change.",
		supporting_memory_ids=[],
		insufficient_evidence=True,
	)
	explainer, _, _ = make_explainer([source], draft)

	result = explainer.explain(
		"technova-deal",
		"Offer a 20 percent annual discount.",
	)

	assert result.insufficient_evidence is True
	assert "not enough" in result.reason.casefold() or "does not address" in result.reason.casefold()
	assert result.supporting_memories == []


def test_empty_memory_result_returns_insufficient_without_calling_groq():
	draft = RecommendationWhyDraft()
	explainer, memory_client, groq_mock = make_explainer([], draft)

	result = explainer.explain("technova-deal", "Prepare the security packet.")

	assert result.insufficient_evidence is True
	assert result.supporting_memories == []
	assert result.conflicting_memories == []
	memory_client.recall_memory.assert_called_once()
	groq_mock.chat.completions.create.assert_not_called()


def test_memories_from_other_deals_are_not_given_to_groq_or_cited():
	unrelated = memory(
		"other-memory",
		"OtherCo has a recurring ERP integration problem.",
		deal_id="other-deal",
	)
	draft = RecommendationWhyDraft(insufficient_evidence=True)
	explainer, _, groq_mock = make_explainer([unrelated], draft)

	result = explainer.explain("technova-deal", "Prepare integration details.")

	assert result.insufficient_evidence is True
	assert result.supporting_memories == []
	groq_mock.chat.completions.create.assert_not_called()


def test_conflicting_memories_are_reported_separately():
	positive = memory("signal-1", "TechNova's CTO said the ERP integration looks straightforward.")
	negative = memory("concern-2", "TechNova's CTO said ERP integration remains a blocker.")
	draft = RecommendationWhyDraft(
		reason="The integration outlook is mixed: an earlier positive signal conflicts with a later blocker.",
		supporting_memory_ids=["signal-1"],
		conflicting_memory_ids=["concern-2"],
	)
	explainer, _, _ = make_explainer([positive, negative], draft)

	result = explainer.explain(
		"technova-deal",
		"Treat ERP integration as ready for sign-off.",
	)

	assert result.insufficient_evidence is False
	assert [item.memory_id for item in result.supporting_memories] == ["signal-1"]
	assert [item.memory_id for item in result.conflicting_memories] == ["concern-2"]


def test_ungrounded_memory_ids_are_rejected():
	source = memory("memory-1", "TechNova is evaluating integration options.")
	draft = RecommendationWhyDraft(
		reason="The recommendation follows an alleged concern.",
		supporting_memory_ids=["invented-memory"],
	)
	explainer, _, _ = make_explainer([source], draft)

	with pytest.raises(RecommendationError, match="not returned by Hindsight"):
		explainer.explain("technova-deal", "Prepare integration documentation.")