"""Mocked Deal Autopsy tests; no Groq or Hindsight network calls."""

import json
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
from groq import Groq

from backend.memory.hindsight_client import HindsightMemoryClient
from Hindsight.ai.deal_autopsy import (
    DealAutopsyAnalyzer,
    DealAutopsyDraft,
    DealAutopsyError,
)
from Hindsight.memory.learning import ObservedOutcomeFact, OutcomeLesson


def memory(memory_id: str, text: str, deal_id: str = "deal-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=memory_id,
        text=text,
        type="world",
        metadata={
            "deal_id": deal_id,
            "customer_name": "TechNova",
            "memory_type": "objection",
            "interaction_date": "2026-09-20T10:00:00Z",
        },
        tags=[f"deal:{deal_id}"],
        occurred_start=None,
        mentioned_at=None,
    )


def analyzer(
    draft: DealAutopsyDraft, memories: list[SimpleNamespace] | None = None
) -> tuple[DealAutopsyAnalyzer, Mock, Mock]:
    hindsight = Mock(spec=HindsightMemoryClient)
    hindsight.recall_memory.return_value = SimpleNamespace(
        results=(memories if memories is not None else [
            memory("m1", "The CTO raised a security concern."),
            memory("m2", "Procurement discussed pricing."),
        ])
    )
    groq = Mock()
    groq.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=draft.model_dump_json(), refusal=None
        ))]
    )
    return (
        DealAutopsyAnalyzer(
            memory_client=cast(HindsightMemoryClient, hindsight),
            groq_client=cast(Groq, groq),
            model="mock-model",
        ),
        hindsight,
        groq,
    )


def test_autopsy_returns_requested_sections_and_only_deal_evidence():
    draft = DealAutopsyDraft(
        customer_company="TechNova",
        timeline=[],
        major_objections=[],
        stakeholder_concerns=[],
        competitors=[],
        pricing_discussions=[],
        customer_requirements=[],
        turning_points=[],
        actions_taken=[],
        resolved_issues=[],
        unresolved_issues=[],
        observed_factors=[ObservedOutcomeFact(
            statement="Security approval remained unresolved.",
            supporting_memory_ids=["m1"],
        )],
        interpretations=[],
        lessons_learned=[OutcomeLesson(
            content="Verify security approval earlier.",
            evidence_basis="inferred",
            supporting_memory_ids=["m1"],
        )],
    )
    service, hindsight, groq = analyzer(
        draft,
        [memory("m1", "The CTO raised a security concern."),
         memory("other", "OtherCo had a risk.", "other-deal")],
    )

    result = service.analyze("deal-1", "lost")

    assert result.deal_id == "deal-1"
    assert result.outcome.value == "lost"
    assert result.customer_company == "TechNova"
    assert [item.memory_id for item in result.supporting_evidence] == ["m1"]
    payload = json.loads(groq.chat.completions.create.call_args.kwargs["messages"][1]["content"])
    assert len(payload["deal_memories"]) == 1
    assert hindsight.recall_memory.call_args.kwargs["tags"] == ["deal:deal-1"]


def test_empty_history_is_insufficient_without_groq_call():
    service, _, groq = analyzer(DealAutopsyDraft(), memories=[])

    result = service.analyze("deal-1", "stalled")

    assert result.insufficient_evidence is True
    assert result.supporting_evidence == []
    groq.chat.completions.create.assert_not_called()


def test_causal_interpretation_requires_explicit_causal_source():
    draft = DealAutopsyDraft(interpretations=[OutcomeLesson(
        content="The security concern caused the loss.",
        evidence_basis="inferred",
        supporting_memory_ids=["m1"],
    )])
    service, _, _ = analyzer(draft)

    with pytest.raises(DealAutopsyError, match="explicit causal evidence"):
        service.analyze("deal-1", "lost")


def test_invalid_outcome_is_rejected():
    service, _, _ = analyzer(DealAutopsyDraft())

    with pytest.raises(ValueError, match="won, lost, or stalled"):
        service.analyze("deal-1", "unknown")
