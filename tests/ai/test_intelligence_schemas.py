"""Deterministic validation tests for intelligence result contracts."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from Hindsight.ai.intelligence_schemas import (
	ClaimKind,
	DealAutopsy,
	DealOutcome,
	Evidence,
	Insight,
	NextBestActionResult,
	ObjectionEvolution,
	ObjectionEvolutionResult,
	ObjectionState,
	ObjectionTransition,
	Pattern,
	Recommendation,
	SimilarDeal,
	SimilarDealsResult,
	WhatChangedResult,
	WinningLossPatternsResult,
)
from Hindsight.memory.memory_schema import MemoryType


@pytest.fixture
def evidence() -> Evidence:
	return Evidence(
		memory_id="memory-1",
		deal_id="deal-1",
		memory_type=MemoryType.OBJECTION,
		content="The CTO raised an API integration concern.",
		timestamp=datetime(2026, 9, 28, tzinfo=timezone.utc),
	)


def test_valid_results_can_be_created(evidence: Evidence):
	insight = Insight(
		statement="The CTO raised an API integration concern.",
		kind=ClaimKind.OBSERVED_FACT,
		evidence=[evidence],
	)
	assert WhatChangedResult(deal_id="deal-1", insights=[insight]).insights == [insight]
	assert NextBestActionResult(
		deal_id="deal-1",
		recommendations=[
			Recommendation(action="Prepare an API overview", reason="Address the concern")
		],
	).recommendations
	assert SimilarDealsResult(
		deal_id="deal-1",
		similar_deals=[
			SimilarDeal(
				deal_id="deal-2",
				similarity_explanation="Both deals had an integration review.",
				matching_characteristics=["ERP integration"],
				evidence=[evidence.model_copy(update={"deal_id": "deal-2"})],
			)
		],
	).similar_deals
	assert ObjectionEvolutionResult(
		deal_id="deal-1",
		objections=[ObjectionEvolution(objection="API integration", transitions=[])],
	).objections
	assert WinningLossPatternsResult(patterns=[Pattern(description="Observed pattern")]).patterns
	assert DealAutopsy(deal_id="deal-1", outcome=DealOutcome.WON).outcome == DealOutcome.WON


def test_required_fields_are_validated():
	with pytest.raises(ValidationError):
		Evidence(deal_id="deal-1", memory_type=MemoryType.OBJECTION, content="Concern")
	with pytest.raises(ValidationError):
		Insight(kind=ClaimKind.OBSERVED_FACT)
	with pytest.raises(ValidationError):
		Recommendation(action="Prepare", reason=" ")
	with pytest.raises(ValidationError):
		SimilarDeal(similarity_explanation="Comparable")
	with pytest.raises(ValidationError):
		ObjectionEvolution()
	with pytest.raises(ValidationError):
		DealAutopsy(outcome=DealOutcome.WON)


def test_evidence_attaches_to_insight_and_requires_an_existing_memory_id(evidence: Evidence):
	insight = Insight(
		statement="Integration risk was raised.",
		kind=ClaimKind.OBSERVED_FACT,
		evidence=[evidence],
	)
	assert insight.evidence[0].memory_id == "memory-1"
	with pytest.raises(ValidationError):
		Evidence(memory_id=" ", deal_id="deal-1", memory_type="objection", content="Text")


def test_recommendation_can_express_uncertainty_and_limitations(evidence: Evidence):
	recommendation = Recommendation(
		action="Schedule an integration review",
		reason="The CTO raised integration concerns.",
		unresolved_issue_or_opportunity="Compatibility remains unconfirmed.",
		evidence=[evidence],
		uncertainty="No technical validation result is recorded.",
		limitations=["Only one interaction is represented."],
	)
	assert recommendation.uncertainty
	assert recommendation.limitations


def test_similar_deal_supports_outcome_and_evidence_backed_lesson(evidence: Evidence):
	lesson = Insight(
		statement="Integration validation was completed before procurement.",
		kind=ClaimKind.OBSERVED_FACT,
		evidence=[evidence],
	)
	deal = SimilarDeal(
		deal_id="deal-2",
		similarity_explanation="Similar integration requirement and buyer committee.",
		matching_characteristics=["integration requirement", "procurement review"],
		outcome=DealOutcome.WON,
		lesson=lesson,
		evidence=[evidence.model_copy(update={"deal_id": "deal-2"})],
	)
	assert deal.outcome == DealOutcome.WON
	assert deal.lesson == lesson


def test_objection_transition_accepts_evidence():
	item = Evidence(
		memory_id="memory-2",
		deal_id="deal-1",
		memory_type=MemoryType.OBJECTION,
		content="The CTO confirmed integration concerns were resolved.",
	)
	transition = ObjectionTransition(
		from_state=ObjectionState.UNRESOLVED,
		to_state=ObjectionState.RESOLVED,
		evidence=[item],
	)
	assert transition.evidence[0].memory_id == "memory-2"
	assert ObjectionTransition(
		to_state=ObjectionState.UNRESOLVED,
		uncertainty="No later interaction was available.",
	).evidence == []


def test_pattern_separates_observed_pattern_from_interpretation(evidence: Evidence):
	pattern = Pattern(
		description="Deals with early integration reviews had recorded positive outcomes.",
		observations=[
			Insight(
				statement="Deal-1 closed after an integration review.",
				kind=ClaimKind.OBSERVED_FACT,
				evidence=[evidence],
			)
		],
		observed_outcomes=[DealOutcome.WON],
		supporting_deal_ids=["deal-1"],
		evidence=[evidence],
		interpretation="Early review may help address technical risk.",
		interpretation_evidence=[evidence],
		uncertainty="One deal is insufficient to establish a trend.",
	)
	assert pattern.observations[0].kind == ClaimKind.OBSERVED_FACT
	assert pattern.interpretation
	assert pattern.uncertainty


def test_autopsy_separates_facts_interpretations_and_lessons(evidence: Evidence):
	autopsy = DealAutopsy(
		deal_id="deal-1",
		outcome=DealOutcome.LOST,
		observed_factors=[
			Insight(
				statement="Procurement requested a lower annual price.",
				kind=ClaimKind.OBSERVED_FACT,
				evidence=[evidence],
			)
		],
		interpretations=[
			Insight(
				statement="Price may have affected the decision.",
				kind=ClaimKind.INTERPRETATION,
				evidence=[evidence],
				uncertainty="The recorded notes do not state the loss reason.",
			)
		],
		lessons=[
			Insight(
				statement="Confirm procurement's price criteria earlier.",
				kind=ClaimKind.INTERPRETATION,
				evidence=[evidence],
			)
		],
		evidence=[evidence],
	)
	assert autopsy.observed_factors[0].kind == ClaimKind.OBSERVED_FACT
	assert autopsy.interpretations[0].kind == ClaimKind.INTERPRETATION
	assert autopsy.lessons[0].kind == ClaimKind.INTERPRETATION


def test_empty_or_insufficient_evidence_is_representable_without_claims():
	changed = WhatChangedResult(
		deal_id="deal-1",
		insufficient_evidence=True,
		limitations=["No dated interaction memories were returned."],
	)
	pattern = Pattern(
		description="No supported pattern available.",
		insufficient_evidence=True,
		uncertainty="Too few deals have known outcomes.",
	)
	autopsy = DealAutopsy(
		deal_id="deal-1",
		outcome=DealOutcome.UNKNOWN,
		insufficient_evidence=True,
	)
	assert changed.insights == [] and changed.insufficient_evidence
	assert pattern.evidence == [] and pattern.insufficient_evidence
	assert autopsy.evidence == [] and autopsy.insufficient_evidence
