"""Mocked chronological change-analysis tests for the synthetic TechNova deal."""

import json
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
from groq import Groq

from backend.memory.hindsight_client import HindsightMemoryClient
from Hindsight.ai.deal_changes import (
    ChangeCategory,
    ChangeType,
    DealChange,
    DealChangeAnalysis,
    DealChangeAnalyzer,
    DealChangeDraft,
)

DEAL_ID = "technova-deal"


def memory(
    memory_id: str,
    content: str,
    *,
    date: str,
    memory_type: str,
    interaction_id: str,
    deal_id: str = DEAL_ID,
    stakeholder_name: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=memory_id,
        text=content,
        type="world",
        metadata={
            "deal_id": deal_id,
            "memory_type": memory_type,
            "customer_name": "TechNova" if deal_id == DEAL_ID else "OtherCo",
            "interaction_date": date,
            "interaction_source": "discovery meeting",
            "interaction_id": interaction_id,
            "stakeholder_name": stakeholder_name,
        },
        tags=[f"deal:{deal_id}"],
        occurred_start=date,
        mentioned_at=None,
    )


def make_groq_client(draft: DealChangeDraft) -> tuple[Groq, Mock]:
    client = Mock()
    message = SimpleNamespace(content=draft.model_dump_json(), refusal=None)
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=message)]
    )
    return cast(Groq, client), client


def make_analyzer(
    memories: list[SimpleNamespace], draft: DealChangeDraft | None = None
) -> tuple[DealChangeAnalyzer, Mock, Mock]:
    memory_client = Mock(spec=HindsightMemoryClient)
    memory_client.recall_memory.return_value = SimpleNamespace(results=memories)
    groq_client, groq_mock = make_groq_client(draft or DealChangeDraft())
    analyzer = DealChangeAnalyzer(
        memory_client=cast(HindsightMemoryClient, memory_client),
        groq_client=groq_client,
        model="mock-model",
    )
    return analyzer, memory_client, groq_mock


def test_new_objection_is_reported_with_later_evidence():
    evidence = [
        memory(
            "old-context",
            "TechNova was reviewing the proposal.",
            date="2026-09-01T10:00:00Z",
            memory_type="important_fact",
            interaction_id="meeting-1",
        ),
        memory(
            "new-objection",
            "The CTO raised an ERP integration objection.",
            date="2026-09-10T10:00:00Z",
            memory_type="objection",
            interaction_id="meeting-2",
            stakeholder_name="CTO",
        ),
    ]
    draft = DealChangeDraft(
        changes=[
            DealChange(
                change_type=ChangeType.NEW,
                category=ChangeCategory.OBJECTION,
                summary="A new ERP integration objection was raised.",
                evidence_basis="observed",
                later_memory_ids=["new-objection"],
            )
        ]
    )
    analyzer, _, _ = make_analyzer(evidence, draft)

    result = analyzer.analyze(DEAL_ID)

    assert result.insufficient_history is False
    assert result.changes[0].change_type == ChangeType.NEW
    assert [item.memory_id for item in result.evidence] == ["new-objection"]


def test_resolved_objection_uses_earlier_and_later_memories():
    evidence = [
        memory(
            "resolved-later",
            "The CTO approved the proposed ERP integration approach.",
            date="2026-09-20T10:00:00Z",
            memory_type="important_fact",
            interaction_id="meeting-2",
            stakeholder_name="CTO",
        ),
        memory(
            "concern-earlier",
            "The CTO was concerned about ERP integration.",
            date="2026-09-10T10:00:00Z",
            memory_type="objection",
            interaction_id="meeting-1",
            stakeholder_name="CTO",
        ),
    ]
    draft = DealChangeDraft(
        changes=[
            DealChange(
                change_type=ChangeType.RESOLVED,
                category=ChangeCategory.OBJECTION,
                summary="The ERP integration concern was resolved after approval.",
                evidence_basis="observed",
                earlier_memory_ids=["concern-earlier"],
                later_memory_ids=["resolved-later"],
            )
        ]
    )
    analyzer, _, _ = make_analyzer(evidence, draft)

    result = analyzer.analyze(DEAL_ID)

    assert result.changes[0].change_type == ChangeType.RESOLVED
    assert {item.memory_id for item in result.evidence} == {
        "concern-earlier",
        "resolved-later",
    }


def test_continuing_objection_is_reported_across_interactions():
    evidence = [
        memory(
            "concern-1",
            "The CTO is concerned about ERP integration.",
            date="2026-09-01T10:00:00Z",
            memory_type="stakeholder_concern",
            interaction_id="meeting-1",
            stakeholder_name="CTO",
        ),
        memory(
            "concern-2",
            "The CTO still needs confirmation about ERP integration.",
            date="2026-09-20T10:00:00Z",
            memory_type="objection",
            interaction_id="meeting-2",
            stakeholder_name="CTO",
        ),
    ]
    draft = DealChangeDraft(
        changes=[
            DealChange(
                change_type=ChangeType.CONTINUING,
                category=ChangeCategory.OBJECTION,
                summary="ERP integration remains a concern for the CTO.",
                evidence_basis="observed",
                earlier_memory_ids=["concern-1"],
                later_memory_ids=["concern-2"],
            )
        ]
    )
    analyzer, _, _ = make_analyzer(evidence, draft)

    result = analyzer.analyze(DEAL_ID)

    assert result.changes[0].change_type == ChangeType.CONTINUING
    assert len(result.evidence) == 2


def test_new_stakeholder_uses_later_interaction_evidence():
    evidence = [
        memory(
            "cto-first",
            "The CTO reviewed the product.",
            date="2026-09-01T10:00:00Z",
            memory_type="stakeholder",
            interaction_id="meeting-1",
            stakeholder_name="CTO",
        ),
        memory(
            "procurement-later",
            "Sarah from procurement joined the discussion.",
            date="2026-09-20T10:00:00Z",
            memory_type="stakeholder",
            interaction_id="meeting-2",
            stakeholder_name="Sarah",
        ),
    ]
    draft = DealChangeDraft(
        changes=[
            DealChange(
                change_type=ChangeType.NEW,
                category=ChangeCategory.STAKEHOLDER,
                summary="Sarah from procurement became involved.",
                evidence_basis="observed",
                later_memory_ids=["procurement-later"],
            )
        ]
    )
    analyzer, _, _ = make_analyzer(evidence, draft)

    result = analyzer.analyze(DEAL_ID)

    assert result.changes[0].category == ChangeCategory.STAKEHOLDER
    assert result.evidence[0].stakeholder_name == "Sarah"


def test_pricing_change_cites_both_amounts():
    evidence = [
        memory(
            "price-old",
            "Annual pricing discussed at $80,000.",
            date="2026-09-01T10:00:00Z",
            memory_type="pricing_discussion",
            interaction_id="meeting-1",
        ),
        memory(
            "price-new",
            "The revised annual price is $100,000.",
            date="2026-09-20T10:00:00Z",
            memory_type="pricing_discussion",
            interaction_id="meeting-2",
        ),
    ]
    draft = DealChangeDraft(
        changes=[
            DealChange(
                change_type=ChangeType.CHANGED,
                category=ChangeCategory.PRICING,
                summary="Annual pricing changed from $80,000 to $100,000.",
                evidence_basis="observed",
                earlier_memory_ids=["price-old"],
                later_memory_ids=["price-new"],
            )
        ]
    )
    analyzer, _, _ = make_analyzer(evidence, draft)

    result = analyzer.analyze(DEAL_ID)

    assert result.changes[0].category == ChangeCategory.PRICING
    assert len(result.evidence) == 2


def test_newly_unresolved_issue_is_reported_from_later_memory():
    evidence = [
        memory(
            "status-old",
            "The security review had not started.",
            date="2026-09-01T10:00:00Z",
            memory_type="important_fact",
            interaction_id="meeting-1",
        ),
        memory(
            "security-open",
            "Security approval is still outstanding.",
            date="2026-09-20T10:00:00Z",
            memory_type="unresolved_question",
            interaction_id="meeting-2",
        ),
    ]
    draft = DealChangeDraft(
        changes=[
            DealChange(
                change_type=ChangeType.UNRESOLVED,
                category=ChangeCategory.UNRESOLVED_ISSUE,
                summary="Security approval remains outstanding.",
                evidence_basis="observed",
                later_memory_ids=["security-open"],
            )
        ]
    )
    analyzer, _, _ = make_analyzer(evidence, draft)

    result = analyzer.analyze(DEAL_ID)

    assert result.changes[0].change_type == ChangeType.UNRESOLVED
    assert result.evidence[0].memory_id == "security-open"


def test_recall_results_are_sorted_chronologically_before_groq():
    newer = memory(
        "meeting-new",
        "TechNova raised a pricing revision request.",
        date="2026-09-20T10:00:00Z",
        memory_type="pricing_discussion",
        interaction_id="meeting-new",
    )
    older = memory(
        "meeting-old",
        "TechNova reviewed the initial proposal.",
        date="2026-09-01T10:00:00Z",
        memory_type="important_fact",
        interaction_id="meeting-old",
    )
    draft = DealChangeDraft()
    analyzer, memory_client, groq_mock = make_analyzer([newer, older], draft)

    analyzer.analyze(DEAL_ID)

    memory_client.recall_memory.assert_called_once()
    payload = json.loads(
        groq_mock.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    )
    assert [item["memory_id"] for item in payload["chronological_memories"]] == [
        "meeting-old",
        "meeting-new",
    ]
    assert memory_client.recall_memory.call_args.kwargs["tags"] == [f"deal:{DEAL_ID}"]


def test_empty_history_returns_insufficient_without_groq_call():
    analyzer, _, groq_mock = make_analyzer([], DealChangeDraft())

    result = analyzer.analyze(DEAL_ID)

    assert result.insufficient_history is True
    assert result.changes == []
    assert result.evidence == []
    assert result.insufficient_reason
    groq_mock.chat.completions.create.assert_not_called()


def test_single_interaction_is_insufficient_historical_information():
    only_memory = memory(
        "only-meeting",
        "The CTO is concerned about integration.",
        date="2026-09-20T10:00:00Z",
        memory_type="objection",
        interaction_id="meeting-only",
    )
    analyzer, _, groq_mock = make_analyzer([only_memory], DealChangeDraft())

    result = analyzer.analyze(DEAL_ID)

    assert result.insufficient_history is True
    assert "two memories" in (result.insufficient_reason or "")
    groq_mock.chat.completions.create.assert_not_called()


def test_unrelated_deal_memories_are_excluded_before_groq():
    unrelated = memory(
        "other-memory",
        "OtherCo resolved an integration concern.",
        date="2026-09-01T10:00:00Z",
        memory_type="objection",
        interaction_id="other-meeting-1",
        deal_id="other-deal",
    )
    unrelated_later = memory(
        "other-memory-later",
        "OtherCo has no remaining integration concern.",
        date="2026-09-20T10:00:00Z",
        memory_type="important_fact",
        interaction_id="other-meeting-2",
        deal_id="other-deal",
    )
    analyzer, _, groq_mock = make_analyzer([unrelated, unrelated_later])

    result = analyzer.analyze(DEAL_ID)

    assert result.insufficient_history is True
    assert result.evidence == []
    groq_mock.chat.completions.create.assert_not_called()