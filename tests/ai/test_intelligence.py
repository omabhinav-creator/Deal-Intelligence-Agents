"""Deterministic tests for the What Changed intelligence service."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from Hindsight.ai.intelligence import (
	_deduplicate_patterns,
	find_similar_deals,
	analyze_patterns,
	get_objection_evolution,
	get_next_best_action,
	what_changed,
)
from Hindsight.ai.intelligence_schemas import (
	ClaimKind,
	DealOutcome,
	Evidence,
	ObjectionState,
	Pattern,
)
from Hindsight.memory.memory_schema import MemoryType


def recalled_memory(
	memory_id: str,
	content: str,
	date: str | None,
	*,
	deal_id: str = "TechNova",
	memory_type: MemoryType = MemoryType.OBJECTION,
	status: str | None = None,
) -> SimpleNamespace:
	metadata = {"deal_id": deal_id, "memory_type": memory_type.value}
	if status is not None:
		metadata["status"] = status
	return SimpleNamespace(
		id=memory_id,
		text=content,
		type="world",
		metadata=metadata,
		tags=[f"deal:{deal_id}", f"type:{memory_type.value}"],
		occurred_start=date,
		mentioned_at=None,
	)


def make_client(memories: list[SimpleNamespace]) -> Mock:
	client = Mock()
	client.recall_memory.return_value = SimpleNamespace(results=memories)
	return client


def test_new_objection_and_continuing_pricing_concern():
	client = make_client(
		[
			recalled_memory("m1", "Pricing concern: annual price is too high.", "2026-09-01T10:00:00Z"),
			recalled_memory("m2", "Pricing concern: annual price remains too high.", "2026-09-28T10:00:00Z"),
			recalled_memory("m3", "Integration concern raised by the CTO.", "2026-09-28T10:00:00Z"),
		]
	)

	result = what_changed("TechNova", client)

	assert result.insufficient_evidence is False
	assert any("objection continues" in item.statement for item in result.insights)
	assert any("new objection" in item.statement for item in result.insights)
	assert all(item.kind == ClaimKind.OBSERVED_FACT for item in result.insights)


def test_new_competitor_is_reported_with_its_source():
	client = make_client(
		[
			recalled_memory("m1", "Pricing concern remains open.", "2026-09-01T10:00:00Z"),
			recalled_memory(
				"m2",
				"Salesforce is being evaluated as a competitor.",
				"2026-09-28T10:00:00Z",
				memory_type=MemoryType.COMPETITOR,
			),
		]
	)

	result = what_changed("TechNova", client)

	competitor_change = next(item for item in result.insights if "competitor" in item.statement)
	assert "new competitor" in competitor_change.statement
	assert [item.memory_id for item in competitor_change.evidence] == ["m2"]


def test_continuing_concern_is_not_classified_as_new():
	client = make_client(
		[
			recalled_memory("m1", "Pricing concern is that the annual price is high.", "2026-09-01T10:00:00Z"),
			recalled_memory("m2", "Pricing concern: annual price is still high.", "2026-09-28T10:00:00Z"),
		]
	)

	result = what_changed("TechNova", client)

	assert len(result.insights) == 1
	assert "continues" in result.insights[0].statement
	assert "new" not in result.insights[0].statement
	assert {item.memory_id for item in result.insights[0].evidence} == {"m1", "m2"}


def test_memories_without_usable_dates_return_insufficient_evidence():
	client = make_client(
		[
			recalled_memory("m1", "Pricing concern is unresolved.", None),
			recalled_memory("m2", "Integration concern is unresolved.", None),
		]
	)

	result = what_changed("TechNova", client)

	assert result.insufficient_evidence is True
	assert result.insights == []
	assert any("timestamp" in item for item in result.limitations)


def test_recall_is_deal_scoped_and_cross_deal_memories_are_filtered():
	client = make_client(
		[
			recalled_memory("tn-old", "Pricing concern remains.", "2026-09-01T10:00:00Z"),
			recalled_memory("tn-new", "Integration concern raised.", "2026-09-28T10:00:00Z"),
			recalled_memory(
				"other-new",
				"Competitor Acme is being evaluated.",
				"2026-09-28T10:00:00Z",
				deal_id="OtherCo",
				memory_type=MemoryType.COMPETITOR,
			),
		]
	)

	result = what_changed("TechNova", client)

	assert client.recall_memory.call_args.kwargs["tags"] == ["deal:TechNova"]
	assert all(
		evidence.deal_id == "TechNova"
		for insight in result.insights
		for evidence in insight.evidence
	)
	assert all(
		"OtherCo" not in evidence.content
		for insight in result.insights
		for evidence in insight.evidence
	)


def test_empty_recall_returns_insufficient_evidence_without_changes():
	result = what_changed("TechNova", make_client([]))

	assert result.insufficient_evidence is True
	assert result.insights == []


def test_every_reported_change_references_actual_recalled_memory_ids():
	memories = [
		recalled_memory("actual-1", "Pricing concern remains open.", "2026-09-01T10:00:00Z"),
		recalled_memory("actual-2", "Salesforce competitor mentioned.", "2026-09-28T10:00:00Z", memory_type=MemoryType.COMPETITOR),
	]
	result = what_changed("TechNova", make_client(memories))
	actual_ids = {item.id for item in memories}

	assert result.insights
	for insight in result.insights:
		assert insight.evidence
		assert {item.memory_id for item in insight.evidence} <= actual_ids


def test_recall_errors_are_not_silently_converted_to_facts():
	client = Mock()
	client.recall_memory.side_effect = RuntimeError("recall unavailable")
	with pytest.raises(RuntimeError, match="recall unavailable"):
		what_changed("TechNova", client)


def test_recall_uses_explicit_deal_query_and_tags():
	client = make_client([])
	what_changed("TechNova", client)
	args = client.recall_memory.call_args
	assert "TechNova" in args.args[0]
	assert args.kwargs["tags"] == ["deal:TechNova"]


@pytest.mark.parametrize(
	("memory_type", "content", "expected_action"),
	[
		(MemoryType.OBJECTION, "The buyer raised an API integration objection.", "objection"),
		(MemoryType.STAKEHOLDER_CONCERN, "The CTO is concerned about data migration.", "stakeholder concern"),
		(MemoryType.PRICING_DISCUSSION, "Procurement requested pricing details.", "pricing discussion"),
		(MemoryType.COMPETITOR, "Salesforce is under evaluation.", "competitive evaluation"),
		(MemoryType.CUSTOMER_REQUEST, "Customer requested a security questionnaire.", "customer request"),
		(MemoryType.BUYING_SIGNAL, "The buyer asked to discuss implementation steps.", "buying signal"),
	])
def test_relevant_memory_produces_evidence_grounded_action(memory_type, content, expected_action):
	client = make_client(
		[recalled_memory("source-1", content, "2026-09-28T10:00:00Z", memory_type=memory_type)]
	)

	result = get_next_best_action("TechNova", client)

	assert result.insufficient_evidence is False
	assert result.recommendations
	recommendation = result.recommendations[0]
	assert expected_action in recommendation.action
	assert content in recommendation.reason
	assert content in recommendation.unresolved_issue_or_opportunity
	assert [item.memory_id for item in recommendation.evidence] == ["source-1"]
	assert content in recommendation.action


def test_no_relevant_memories_returns_insufficient_evidence():
	client = make_client(
		[
			recalled_memory(
				"weak-1",
				"General account note with no actionable deal issue.",
				"2026-09-28T10:00:00Z",
				memory_type=MemoryType.IMPORTANT_FACT,
			)
		]
	)

	result = get_next_best_action("TechNova", client)

	assert result.insufficient_evidence is True
	assert result.recommendations == []


def test_conflicting_statuses_are_preserved_and_not_silently_resolved():
	client = make_client(
		[
			recalled_memory(
				"open-source",
				"API integration objection remains open.",
				"2026-09-27T10:00:00Z",
				status="open",
			),
			recalled_memory(
				"resolved-source",
				"API integration objection marked resolved.",
				"2026-09-28T10:00:00Z",
				status="resolved",
			),
		]
	)

	result = get_next_best_action("TechNova", client)

	assert result.insufficient_evidence is False
	assert len(result.recommendations) == 1
	assert "Verify the current status" in result.recommendations[0].action
	assert "disagree" in result.recommendations[0].reason
	assert result.recommendations[0].uncertainty
	assert {item.memory_id for item in result.recommendations[0].evidence} == {
		"open-source",
		"resolved-source",
	}


def test_cross_deal_memories_are_ignored_for_next_action():
	client = make_client(
		[
			recalled_memory(
				"other-1",
				"Customer requested a pricing proposal.",
				"2026-09-28T10:00:00Z",
				deal_id="OtherCo",
				memory_type=MemoryType.CUSTOMER_REQUEST,
			),
			recalled_memory(
				"tn-1",
				"The CTO raised an API integration concern.",
				"2026-09-28T10:00:00Z",
				memory_type=MemoryType.STAKEHOLDER_CONCERN,
			),
		]
	)

	result = get_next_best_action("TechNova", client)

	assert client.recall_memory.call_args.kwargs["tags"] == ["deal:TechNova"]
	assert all(
		evidence.deal_id == "TechNova"
		for recommendation in result.recommendations
		for evidence in recommendation.evidence
	)
	assert all(
		evidence.memory_id != "other-1"
		for recommendation in result.recommendations
		for evidence in recommendation.evidence
	)


def test_next_action_recall_failure_returns_insufficient_evidence():
	client = Mock()
	client.recall_memory.side_effect = RuntimeError("offline")

	result = get_next_best_action("TechNova", client)

	assert result.insufficient_evidence is True
	assert result.recommendations == []
	assert any("recall failed" in item for item in result.limitations)


def test_next_action_uses_only_memory_facts_and_does_not_claim_a_win():
	content = "The customer requested an API integration review."
	result = get_next_best_action(
		"TechNova",
		make_client(
			[
				recalled_memory(
					"source-1",
					content,
					"2026-09-28T10:00:00Z",
					memory_type=MemoryType.CUSTOMER_REQUEST,
				)
			]
		),
	)
	recommendation = result.recommendations[0]

	assert "requested an API integration review" in recommendation.reason
	assert "source-1" == recommendation.evidence[0].memory_id
	assert "win" not in recommendation.action.casefold()
	assert "will close" not in recommendation.reason.casefold()


def similar_deal_memories() -> tuple[list[SimpleNamespace], list[SimpleNamespace]]:
	current = [
		recalled_memory("tn-price", "Annual subscription price concern: price is high.", None, memory_type=MemoryType.PRICING_DISCUSSION),
		recalled_memory("tn-req", "Requires ERP integration through API.", None, memory_type=MemoryType.CUSTOMER_REQUIREMENT),
		recalled_memory("tn-comp", "Salesforce is considered as a competitor.", None, memory_type=MemoryType.COMPETITOR),
	]
	historical = [
		recalled_memory("ds-price", "Annual subscription price concern: price is high.", None, deal_id="DataSphere", memory_type=MemoryType.PRICING_DISCUSSION),
		recalled_memory("ds-req", "Requires ERP integration through API.", None, deal_id="DataSphere", memory_type=MemoryType.CUSTOMER_REQUIREMENT),
		recalled_memory("ds-comp", "Salesforce is considered as a competitor.", None, deal_id="DataSphere", memory_type=MemoryType.COMPETITOR),
		recalled_memory("ds-outcome", "Deal outcome: won.", None, deal_id="DataSphere", memory_type=MemoryType.DEAL_OUTCOME),
		recalled_memory("ds-lesson", "Technical demo helped resolve integration concerns.", None, deal_id="DataSphere", memory_type=MemoryType.LESSON_LEARNED),
		recalled_memory("cc-risk", "Security certification concern.", None, deal_id="CloudCore", memory_type=MemoryType.RISK),
		recalled_memory("cc-req", "Offline backup requirement.", None, deal_id="CloudCore", memory_type=MemoryType.CUSTOMER_REQUIREMENT),
		recalled_memory("cc-comp", "HubSpot is considered as a competitor.", None, deal_id="CloudCore", memory_type=MemoryType.COMPETITOR),
		recalled_memory("fe-price", "Annual subscription price question.", None, deal_id="FinEdge", memory_type=MemoryType.PRICING_DISCUSSION),
	]
	return current, historical


def make_similar_deal_client(
	current: list[SimpleNamespace], historical: list[SimpleNamespace]
) -> Mock:
	client = Mock()
	client.recall_memory.side_effect = [
		SimpleNamespace(results=current),
		SimpleNamespace(results=historical),
	]
	return client


def test_similar_deal_finder_identifies_datasphere_with_shared_signals():
	current, historical = similar_deal_memories()
	client = make_similar_deal_client(current, historical)

	result = find_similar_deals("TechNova", client)

	assert result.insufficient_evidence is False
	assert [item.deal_id for item in result.similar_deals] == ["DataSphere"]
	assert len(result.similar_deals[0].matching_characteristics) >= 3
	assert any("pricing" in item.casefold() for item in result.similar_deals[0].matching_characteristics)
	assert any("integration" in item.casefold() or "api" in item.casefold() for item in result.similar_deals[0].matching_characteristics)
	assert any("salesforce" in item.casefold() for item in result.similar_deals[0].matching_characteristics)


def test_unrelated_cloudcore_and_self_are_not_returned():
	current, historical = similar_deal_memories()
	result = find_similar_deals("TechNova", make_similar_deal_client(current, historical))

	returned_ids = {item.deal_id for item in result.similar_deals}
	assert "TechNova" not in returned_ids
	assert "CloudCore" not in returned_ids
	assert "DataSphere" in returned_ids


def test_similar_deal_outcome_and_lesson_require_supporting_memories():
	current, historical = similar_deal_memories()
	result = find_similar_deals("TechNova", make_similar_deal_client(current, historical))
	datasphere = result.similar_deals[0]

	assert datasphere.outcome == DealOutcome.WON
	assert any(item.memory_id == "ds-outcome" for item in datasphere.evidence)
	assert datasphere.lesson is not None
	assert "Technical demo helped resolve integration concerns." in datasphere.lesson.statement
	assert [item.memory_id for item in datasphere.lesson.evidence] == ["ds-lesson"]


def test_reference_and_historical_evidence_are_separate_by_deal():
	current, historical = similar_deal_memories()
	result = find_similar_deals("TechNova", make_similar_deal_client(current, historical))
	datasphere = result.similar_deals[0]

	assert datasphere.reference_evidence
	assert {item.deal_id for item in datasphere.reference_evidence} == {"TechNova"}
	assert datasphere.evidence
	assert {item.deal_id for item in datasphere.evidence} == {"DataSphere"}
	assert all(item.deal_id != "DataSphere" for item in datasphere.reference_evidence)
	assert all(item.deal_id != "TechNova" for item in datasphere.evidence)


def test_deal_discovery_uses_scoped_reference_and_unfiltered_historical_recall():
	current, historical = similar_deal_memories()
	client = make_similar_deal_client(current, historical)
	find_similar_deals("TechNova", client)

	assert client.recall_memory.call_args_list[0].kwargs["tags"] == ["deal:TechNova"]
	assert "tags" not in client.recall_memory.call_args_list[1].kwargs


def test_no_identifiable_historical_candidate_returns_insufficient_evidence():
	current, _ = similar_deal_memories()
	result = find_similar_deals(
		"TechNova",
		make_similar_deal_client(current, current),
	)

	assert result.insufficient_evidence is True
	assert result.similar_deals == []


def test_recall_failure_returns_insufficient_evidence():
	client = Mock()
	client.recall_memory.side_effect = [
		SimpleNamespace(results=similar_deal_memories()[0]),
		RuntimeError("offline"),
	]

	result = find_similar_deals("TechNova", client)

	assert result.insufficient_evidence is True
	assert result.similar_deals == []
	assert any("recall failed" in item for item in result.limitations)


def test_partial_overlap_does_not_meet_similarity_threshold():
	current, historical = similar_deal_memories()
	result = find_similar_deals(
		"TechNova",
		make_similar_deal_client(current, [item for item in historical if item.metadata["deal_id"] == "FinEdge"]),
	)

	assert result.insufficient_evidence is True
	assert result.similar_deals == []


def test_outcome_and_lesson_are_unavailable_without_explicit_memories():
	current, historical = similar_deal_memories()
	historical = [
		item for item in historical
		if item.metadata["deal_id"] == "DataSphere"
		and item.metadata["memory_type"] not in {MemoryType.DEAL_OUTCOME.value, MemoryType.LESSON_LEARNED.value}
	]
	result = find_similar_deals("TechNova", make_similar_deal_client(current, historical))

	assert result.similar_deals[0].outcome is None
	assert result.similar_deals[0].lesson is None


def test_each_similarity_claim_has_current_and_historical_evidence():
	current, historical = similar_deal_memories()
	result = find_similar_deals("TechNova", make_similar_deal_client(current, historical))

	for candidate in result.similar_deals:
		assert candidate.matching_characteristics
		assert candidate.reference_evidence
		assert candidate.evidence
		assert all(item.deal_id == "TechNova" for item in candidate.reference_evidence)
		assert all(item.deal_id == candidate.deal_id for item in candidate.evidence)


def test_new_objection_is_marked_as_first_recorded_appearance():
	memory = recalled_memory(
		"new-objection",
		"The buyer raised an API integration objection.",
		"2026-09-28T10:00:00Z",
		memory_type=MemoryType.OBJECTION,
	)
	result = get_objection_evolution("TechNova", make_client([memory]))

	transition = result.objections[0].transitions[0]
	assert transition.to_state == ObjectionState.NEWLY_APPEARING
	assert "first matching mention" in transition.uncertainty
	assert transition.date.isoformat() == "2026-09-28T10:00:00+00:00"


def test_objection_recurring_across_wording_variations():
	client = make_client(
		[
			recalled_memory("price-1", "Pricing concern: annual price is too high.", "2026-09-01T10:00:00Z"),
			recalled_memory("price-2", "The annual pricing objection remains.", "2026-09-15T10:00:00Z"),
		]
	)
	result = get_objection_evolution("TechNova", client)

	assert len(result.objections) == 1
	assert result.objections[0].transitions[-1].to_state == ObjectionState.RECURRING
	assert {item.memory_id for item in result.objections[0].transitions[-1].evidence} == {"price-1", "price-2"}


def test_objection_continues_when_later_memory_repeats_same_issue():
	client = make_client(
		[
			recalled_memory("api-1", "API integration is a concern.", "2026-09-01T10:00:00Z"),
			recalled_memory("api-2", "Concern remains about API integration.", "2026-09-20T10:00:00Z"),
		]
	)
	result = get_objection_evolution("TechNova", client)

	assert result.objections[0].transitions[-1].to_state == ObjectionState.RECURRING
	assert result.objections[0].transitions[-1].uncertainty


def test_objection_resolved_only_when_later_memory_explicitly_says_so():
	client = make_client(
		[
			recalled_memory("sso-1", "Customer raised an SSO concern.", "2026-09-01T10:00:00Z"),
			recalled_memory("sso-2", "Customer confirmed the SSO concern was resolved.", "2026-09-20T10:00:00Z", status="resolved"),
		]
	)
	result = get_objection_evolution("TechNova", client)
	transition = result.objections[0].transitions[-1]

	assert transition.to_state == ObjectionState.RESOLVED
	assert {item.memory_id for item in transition.evidence} == {"sso-1", "sso-2"}


def test_objection_decreases_only_with_explicit_evidence():
	client = make_client(
		[
			recalled_memory("api-1", "ERP integration concern raised.", "2026-09-01T10:00:00Z"),
			recalled_memory("api-2", "ERP integration concern is decreasing.", "2026-09-20T10:00:00Z", status="decreasing"),
		]
	)
	result = get_objection_evolution("TechNova", client)

	assert result.objections[0].transitions[-1].to_state == ObjectionState.DECREASING


def test_disappearing_objection_is_not_marked_resolved():
	client = make_client(
		[
			recalled_memory("price-1", "Annual pricing concern.", "2026-09-01T10:00:00Z"),
			recalled_memory("new-2", "A new stakeholder joined the review.", "2026-09-20T10:00:00Z", memory_type=MemoryType.STAKEHOLDER),
		]
	)
	result = get_objection_evolution("TechNova", client)

	assert result.objections
	assert all(
		transition.to_state != ObjectionState.RESOLVED
		for evolution in result.objections
		for transition in evolution.transitions
	)
	assert result.objections[0].insufficient_evidence is True


def test_multiple_objection_topics_evolve_independently():
	client = make_client(
		[
			recalled_memory("price-1", "Annual pricing concern.", "2026-09-01T10:00:00Z"),
			recalled_memory("api-1", "ERP integration risk.", "2026-09-02T10:00:00Z", memory_type=MemoryType.RISK),
			recalled_memory("price-2", "Annual price objection remains.", "2026-09-20T10:00:00Z"),
			recalled_memory("api-2", "ERP integration risk is worsening.", "2026-09-21T10:00:00Z", memory_type=MemoryType.RISK, status="increasing"),
		]
	)
	result = get_objection_evolution("TechNova", client)

	assert len(result.objections) == 2
	states = {item.transitions[-1].to_state for item in result.objections}
	assert ObjectionState.RECURRING in states
	assert ObjectionState.INCREASING in states


def test_stakeholder_concern_can_evolve_across_related_memory_types():
	client = make_client(
		[
			recalled_memory("migration-1", "Data migration concern raised by CTO.", "2026-09-01T10:00:00Z", memory_type=MemoryType.STAKEHOLDER_CONCERN),
			recalled_memory("migration-2", "CTO's data migration objection remains open.", "2026-09-20T10:00:00Z", memory_type=MemoryType.OBJECTION),
		]
	)
	result = get_objection_evolution("TechNova", client)

	assert len(result.objections) == 1
	assert result.objections[0].transitions[-1].to_state == ObjectionState.RECURRING


def test_conflicting_resolved_and_later_open_evidence_is_preserved():
	client = make_client(
		[
			recalled_memory("integration-1", "Integration objection was resolved.", "2026-09-01T10:00:00Z", status="resolved"),
			recalled_memory("integration-2", "Integration objection remains unresolved.", "2026-09-20T10:00:00Z", status="unresolved"),
		]
	)
	result = get_objection_evolution("TechNova", client)
	transition = result.objections[0].transitions[-1]

	assert transition.to_state == ObjectionState.UNRESOLVED
	assert transition.uncertainty
	assert {item.memory_id for item in transition.evidence} == {"integration-1", "integration-2"}


def test_missing_timestamps_return_insufficient_evidence_without_dates():
	client = make_client(
		[
			recalled_memory("security-1", "Security review concern.", None),
			recalled_memory("security-2", "Security review concern remains open.", None),
		]
	)
	result = get_objection_evolution("TechNova", client)

	assert result.insufficient_evidence is True
	assert result.objections == []
	assert any("timestamp" in item for item in result.limitations)


def test_objection_evolution_ignores_other_deals():
	client = make_client(
		[
			recalled_memory("tn-1", "API integration objection.", "2026-09-01T10:00:00Z"),
			recalled_memory("other-2", "API integration objection remains unresolved.", "2026-09-20T10:00:00Z", deal_id="OtherCo"),
		]
	)
	result = get_objection_evolution("TechNova", client)

	assert client.recall_memory.call_args.kwargs["tags"] == ["deal:TechNova"]
	assert result.insufficient_evidence is True
	assert all(
		evidence.deal_id == "TechNova"
		for evolution in result.objections
		for transition in evolution.transitions
		for evidence in transition.evidence
	)


def test_no_objection_memories_returns_insufficient_evidence():
	client = make_client(
		[
			recalled_memory("stakeholder-1", "A new stakeholder joined.", "2026-09-20T10:00:00Z", memory_type=MemoryType.STAKEHOLDER),
		]
	)
	result = get_objection_evolution("TechNova", client)

	assert result.insufficient_evidence is True
	assert result.objections == []


def test_objection_evolution_recall_failure_returns_insufficient_evidence():
	client = Mock()
	client.recall_memory.side_effect = RuntimeError("offline")
	result = get_objection_evolution("TechNova", client)

	assert result.insufficient_evidence is True
	assert result.objections == []
	assert any("recall failed" in item for item in result.limitations)


def test_every_objection_transition_has_actual_evidence_and_date():
	memories = [
		recalled_memory("objection-1", "Annual pricing objection.", "2026-09-01T10:00:00Z"),
		recalled_memory("objection-2", "Annual pricing concern remains unresolved.", "2026-09-20T10:00:00Z"),
	]
	result = get_objection_evolution("TechNova", make_client(memories))
	actual = {item.id: item for item in memories}

	for evolution in result.objections:
		for transition in evolution.transitions:
			assert transition.evidence
			assert transition.date is not None
			for evidence in transition.evidence:
				assert evidence.memory_id in actual
				assert evidence.timestamp is not None


def test_no_resolution_or_timestamp_is_fabricated():
	memories = [
		recalled_memory("objection-1", "ERP integration concern.", "2026-09-01T10:00:00Z"),
		recalled_memory("unrelated-2", "Procurement joined the discussion.", "2026-09-20T10:00:00Z", memory_type=MemoryType.STAKEHOLDER),
	]
	result = get_objection_evolution("TechNova", make_client(memories))

	assert all(
		transition.to_state != ObjectionState.RESOLVED
		for evolution in result.objections
		for transition in evolution.transitions
	)
	assert all(
		transition.date.isoformat().startswith("2026-09-")
		for evolution in result.objections
		for transition in evolution.transitions
	)


def historical_pattern_memories() -> list[SimpleNamespace]:
	return [
		recalled_memory("won-1-integration", "ERP integration requirement; API integration required.", None, deal_id="WonOne", memory_type=MemoryType.CUSTOMER_REQUIREMENT),
		recalled_memory("won-1-competitor", "Salesforce competitor evaluated.", None, deal_id="WonOne", memory_type=MemoryType.COMPETITOR),
		recalled_memory("won-1-outcome", "Deal outcome: won.", None, deal_id="WonOne", memory_type=MemoryType.DEAL_OUTCOME),
		recalled_memory("won-2-integration", "ERP integration requirement; API integration required.", None, deal_id="WonTwo", memory_type=MemoryType.CUSTOMER_REQUIREMENT),
		recalled_memory("won-2-competitor", "Salesforce competitor evaluated.", None, deal_id="WonTwo", memory_type=MemoryType.COMPETITOR),
		recalled_memory("won-2-outcome", "Deal outcome: won.", None, deal_id="WonTwo", memory_type=MemoryType.DEAL_OUTCOME),
		recalled_memory("lost-1-price", "Annual subscription price concern; price is high.", None, deal_id="LostOne", memory_type=MemoryType.PRICING_DISCUSSION),
		recalled_memory("lost-1-competitor", "Salesforce competitor evaluated.", None, deal_id="LostOne", memory_type=MemoryType.COMPETITOR),
		recalled_memory("lost-1-outcome", "Deal outcome: lost.", None, deal_id="LostOne", memory_type=MemoryType.DEAL_OUTCOME),
		recalled_memory("lost-2-price", "Annual subscription price concern; price is high.", None, deal_id="LostTwo", memory_type=MemoryType.PRICING_DISCUSSION),
		recalled_memory("lost-2-competitor", "Salesforce competitor evaluated.", None, deal_id="LostTwo", memory_type=MemoryType.COMPETITOR),
		recalled_memory("lost-2-outcome", "Deal outcome: lost.", None, deal_id="LostTwo", memory_type=MemoryType.DEAL_OUTCOME),
		recalled_memory("stalled-1-risk", "Security review delay remains a risk.", None, deal_id="StalledOne", memory_type=MemoryType.RISK),
		recalled_memory("stalled-1-outcome", "Deal outcome: stalled.", None, deal_id="StalledOne", memory_type=MemoryType.DEAL_OUTCOME),
		recalled_memory("stalled-2-risk", "Security review delay remains a risk.", None, deal_id="StalledTwo", memory_type=MemoryType.RISK),
		recalled_memory("stalled-2-outcome", "Deal outcome: stalled.", None, deal_id="StalledTwo", memory_type=MemoryType.DEAL_OUTCOME),
		recalled_memory("unknown-1-risk", "Security review delay remains a risk.", None, deal_id="UnknownOutcome", memory_type=MemoryType.RISK),
		recalled_memory("won-unique", "Unique procurement workflow requirement.", None, deal_id="WonOne", memory_type=MemoryType.CUSTOMER_REQUIREMENT),
	]


def test_analyze_patterns_finds_recurring_won_characteristic():
	client = make_client(historical_pattern_memories())
	result = analyze_patterns(client)

	assert any(
		pattern.observed_outcomes == [DealOutcome.WON]
		and "integration" in pattern.description.casefold()
		for pattern in result.patterns
	)


def test_analyze_patterns_finds_recurring_lost_characteristic():
	result = analyze_patterns(make_client(historical_pattern_memories()))

	assert any(
		pattern.observed_outcomes == [DealOutcome.LOST]
		and pattern.supporting_deal_ids == ["LostOne", "LostTwo"]
		and "price" in pattern.description.casefold()
		for pattern in result.patterns
	)


def test_analyze_patterns_keeps_stalled_outcome_separate():
	result = analyze_patterns(make_client(historical_pattern_memories()))

	assert any(
		pattern.observed_outcomes == [DealOutcome.STALLED]
		and set(pattern.supporting_deal_ids) == {"StalledOne", "StalledTwo"}
		for pattern in result.patterns
	)
	assert all(
		pattern.observed_outcomes != [DealOutcome.OPEN]
		for pattern in result.patterns
	)


def test_single_deal_characteristic_is_not_reported_as_a_pattern():
	result = analyze_patterns(make_client(historical_pattern_memories()))

	assert not any("procurement" in pattern.description.casefold() for pattern in result.patterns)


def test_missing_outcome_is_not_assumed_to_be_lost():
	memories = [
		recalled_memory("unknown-risk", "Security review delay risk.", None, deal_id="NoOutcome", memory_type=MemoryType.RISK),
		recalled_memory("lost-1", "Security review delay risk.", None, deal_id="LostOne", memory_type=MemoryType.RISK),
		recalled_memory("lost-1-outcome", "Deal outcome: lost.", None, deal_id="LostOne", memory_type=MemoryType.DEAL_OUTCOME),
		recalled_memory("lost-2", "Security review delay risk.", None, deal_id="LostTwo", memory_type=MemoryType.RISK),
		recalled_memory("lost-2-outcome", "Deal outcome: lost.", None, deal_id="LostTwo", memory_type=MemoryType.DEAL_OUTCOME),
	]
	result = analyze_patterns(make_client(memories))

	assert result.patterns
	assert all("NoOutcome" not in pattern.supporting_deal_ids for pattern in result.patterns)
	assert all(
		item.deal_id != "NoOutcome"
		for pattern in result.patterns
		for item in pattern.evidence
	)


def test_mixed_outcome_characteristic_preserves_uncertainty():
	result = analyze_patterns(make_client(historical_pattern_memories()))
	mixed = [
		pattern
		for pattern in result.patterns
		if "salesforce" in pattern.description.casefold()
	]

	assert {pattern.observed_outcomes[0] for pattern in mixed} == {DealOutcome.WON, DealOutcome.LOST}
	assert all(pattern.uncertainty for pattern in mixed)
	assert all(pattern.other_outcome_evidence for pattern in mixed)


def test_patterns_are_observations_not_causal_claims_or_unsupported_hypotheses():
	result = analyze_patterns(make_client(historical_pattern_memories()))

	assert result.patterns
	for pattern in result.patterns:
		assert pattern.observations
		assert pattern.interpretation
		assert "does not establish" in pattern.interpretation
		assert pattern.hypothesis is None
		assert "cause" not in pattern.description.casefold()


def test_every_pattern_has_evidence_from_multiple_matching_deals():
	result = analyze_patterns(make_client(historical_pattern_memories()))

	for pattern in result.patterns:
		assert len(pattern.supporting_deal_ids) >= 2
		assert pattern.evidence
		assert {item.deal_id for item in pattern.evidence} == set(pattern.supporting_deal_ids)
		assert all(observation.evidence for observation in pattern.observations)


def test_duplicate_patterns_merge_occurrences_deals_and_evidence():
	first = Pattern(
		description="Early stakeholder alignment improves deal progress",
		observed_outcomes=[DealOutcome.WON],
		supporting_deal_ids=["DealA"],
		evidence=[Evidence(memory_id="m1", deal_id="DealA", memory_type=MemoryType.BUYING_SIGNAL, content="Alignment")],
	)
	second = Pattern(
		description="  EARLY stakeholder alignment improves deal progress! ",
		observed_outcomes=[DealOutcome.WON],
		supporting_deal_ids=["DealB"],
		evidence=[Evidence(memory_id="m2", deal_id="DealB", memory_type=MemoryType.BUYING_SIGNAL, content="Alignment")],
	)

	result = _deduplicate_patterns([first, second])

	assert len(result) == 1
	assert result[0].description == first.description
	assert result[0].occurrence_count == 2
	assert result[0].supporting_deal_ids == ["DealA", "DealB"]
	assert {item.memory_id for item in result[0].evidence} == {"m1", "m2"}


def test_patterns_sharing_words_but_different_claims_stay_separate():
	patterns = [
		Pattern(description="Early stakeholder alignment improves deal progress"),
		Pattern(description="Late stakeholder alignment delays deal progress"),
	]

	assert len(_deduplicate_patterns(patterns)) == 2


def test_analyzer_groups_reworded_claims_and_keeps_different_claim_separate():
	memories = []
	claims = [
		"Early stakeholder alignment improves deal progress.",
		"Early stakeholder engagement helps move deals forward.",
		"Engaging stakeholders early improves deal progression.",
	]
	for index, claim in enumerate(claims, start=1):
		deal_id = f"Won{index}"
		memories.append(recalled_memory(f"claim-{index}", claim, None, deal_id=deal_id, memory_type=MemoryType.CUSTOMER_REQUIREMENT))
		memories.append(recalled_memory(f"outcome-{index}", "Deal outcome: won.", None, deal_id=deal_id, memory_type=MemoryType.DEAL_OUTCOME))
		if index < 3:
			memories.append(recalled_memory(f"risk-{index}", "Early stakeholder alignment reduces pricing risk.", None, deal_id=deal_id, memory_type=MemoryType.CUSTOMER_REQUIREMENT))

	result = analyze_patterns(make_client(memories))

	assert len(result.patterns) == 2
	alignment = next(pattern for pattern in result.patterns if "improves deal progress" in pattern.description)
	pricing_risk = next(pattern for pattern in result.patterns if "reduces pricing risk" in pattern.description)
	assert alignment.occurrence_count == 3
	assert set(alignment.supporting_deal_ids) == {"Won1", "Won2", "Won3"}
	assert len(alignment.evidence) == 3
	assert pricing_risk.occurrence_count == 2
	assert set(pricing_risk.supporting_deal_ids) == {"Won1", "Won2"}


def test_historical_deal_evidence_remains_grouped_by_deal():
	client = make_client(historical_pattern_memories())
	result = analyze_patterns(client)

	assert "tags" not in client.recall_memory.call_args.kwargs
	for pattern in result.patterns:
		assert all(item.deal_id in pattern.supporting_deal_ids for item in pattern.evidence)
		assert all(item.memory_type != MemoryType.DEAL_OUTCOME for item in pattern.observations[0].evidence)


def test_pattern_recall_failure_returns_insufficient_evidence():
	client = Mock()
	client.recall_memory.side_effect = RuntimeError("offline")
	result = analyze_patterns(client)

	assert result.insufficient_evidence is True
	assert result.patterns == []
	assert any("recall failed" in item for item in result.limitations)


def test_too_few_explicit_outcomes_returns_insufficient_evidence():
	memories = [
		recalled_memory("won-risk", "Security review delay risk.", None, deal_id="WonOnly", memory_type=MemoryType.RISK),
		recalled_memory("won-outcome", "Deal outcome: won.", None, deal_id="WonOnly", memory_type=MemoryType.DEAL_OUTCOME),
		recalled_memory("unknown-risk", "Security review delay risk.", None, deal_id="Unknown", memory_type=MemoryType.RISK),
	]
	result = analyze_patterns(make_client(memories))

	assert result.insufficient_evidence is True
	assert result.patterns == []
	assert any("Fewer than two" in item for item in result.limitations)
