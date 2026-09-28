"""Mocked outcome-learning tests; no Groq or Hindsight network calls."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
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
from Hindsight.ai.deal_changes import EvidenceBasis
from Hindsight.memory.learning import (
    DealOutcome,
    OutcomeLearningDraft,
    OutcomeLearningError,
    OutcomeLearningService,
    ObservedOutcomeFact,
    OutcomeLesson,
)
from Hindsight.memory.memory_schema import MemoryType


def deal_memory(memory_id: str, content: str, *, deal_id: str = "deal-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=memory_id,
        text=content,
        type="world",
        metadata={
            "deal_id": deal_id,
            "memory_type": "stakeholder_concern",
            "customer_name": "TechNova" if deal_id == "deal-1" else "OtherCo",
            "interaction_id": f"meeting-{memory_id}",
            "interaction_date": "2026-09-20T10:00:00Z",
            "interaction_source": "sales meeting",
            "stakeholder_name": "CTO",
        },
        tags=[f"deal:{deal_id}"],
        occurred_start="2026-09-20T10:00:00Z",
        mentioned_at=None,
        document_id=f"meeting-{memory_id}",
    )


def sample_memories() -> list[SimpleNamespace]:
    return [
        deal_memory(
            "security-1",
            "TechNova's CTO raised a security concern in two meetings; approval remains unresolved.",
        ),
        deal_memory(
            "pricing-1",
            "Procurement requested pricing clarification while CompetitorX was in the evaluation.",
        ),
    ]


def sample_draft() -> OutcomeLearningDraft:
    return OutcomeLearningDraft(
        observed_facts=[
            ObservedOutcomeFact(
                statement="A security concern remained unresolved.",
                supporting_memory_ids=["security-1"],
            ),
            ObservedOutcomeFact(
                statement="Procurement asked for pricing clarification while CompetitorX was evaluated.",
                supporting_memory_ids=["pricing-1"],
            ),
        ],
        lessons=[
            OutcomeLesson(
                content=(
                    "The history shows security concerns remained unresolved while "
                    "commercial discussions progressed. Future deals with similar "
                    "security concerns may benefit from addressing security requirements earlier."
                ),
                evidence_basis=EvidenceBasis.INFERRED.value,
                supporting_memory_ids=["security-1", "pricing-1"],
            )
        ],
    )


def make_service(
    *,
    memories: list[SimpleNamespace] | None = None,
    draft: OutcomeLearningDraft | None = None,
) -> tuple[OutcomeLearningService, Mock, Mock]:
    hindsight_sdk = Mock(spec=HindsightMemoryClient)
    hindsight_sdk.recall_memory.return_value = SimpleNamespace(
        results=sample_memories() if memories is None else memories
    )
    hindsight_sdk.retain_memory.return_value = Mock(spec=RetainResponse)

    groq_sdk = Mock()
    message = SimpleNamespace(content=(draft or sample_draft()).model_dump_json(), refusal=None)
    groq_sdk.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=message)]
    )
    service = OutcomeLearningService(
        memory_client=cast(HindsightMemoryClient, hindsight_sdk),
        groq_client=cast(Groq, groq_sdk),
        model="mock-model",
    )
    return service, hindsight_sdk, groq_sdk


@pytest.mark.parametrize("outcome", [DealOutcome.WON, DealOutcome.LOST, DealOutcome.STALLED])
def test_each_supported_outcome_produces_and_stores_a_lesson(outcome: DealOutcome):
    service, hindsight_sdk, groq_sdk = make_service()

    result = service.learn_from_outcome(
        deal_id="deal-1",
        outcome=outcome,
        customer_name="TechNova",
        outcome_date=datetime(2026, 9, 28, tzinfo=timezone.utc),
        interaction_id="close-review-1",
    )

    assert result.outcome == outcome
    assert result.insufficient_evidence is False
    assert len(result.lessons) == 1
    assert len(result.retained_memories) == 2
    assert result.retained_memories[0].memory_type == MemoryType.DEAL_OUTCOME
    assert result.retained_memories[0].status == outcome.value
    lesson_memory = result.retained_memories[1]
    assert lesson_memory.memory_type == MemoryType.LESSON_LEARNED
    assert lesson_memory.deal_id == "deal-1"
    assert lesson_memory.customer_name == "TechNova"
    assert lesson_memory.status == outcome.value
    assert lesson_memory.evidence_basis == "inferred"
    assert lesson_memory.supporting_memory_ids == ["security-1", "pricing-1"]
    assert "Observed facts:" in lesson_memory.content
    assert "Lesson (inferred):" in lesson_memory.content

    assert hindsight_sdk.recall_memory.call_args.kwargs["tags"] == ["deal:deal-1"]
    groq_payload = json.loads(
        groq_sdk.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    )
    assert groq_payload["outcome"] == outcome.value
    assert {item["memory_id"] for item in groq_payload["deal_memories"]} == {
        "security-1",
        "pricing-1",
    }
    assert hindsight_sdk.retain_memory.call_count == 2
    stored_lesson_metadata = hindsight_sdk.retain_memory.call_args.kwargs["metadata"]
    assert stored_lesson_metadata["deal_id"] == "deal-1"
    assert stored_lesson_metadata["memory_type"] == "lesson_learned"
    assert stored_lesson_metadata["status"] == outcome.value
    assert json.loads(stored_lesson_metadata["supporting_memory_ids"]) == [
        "security-1",
        "pricing-1",
    ]


def test_empty_history_records_outcome_but_does_not_call_groq_or_invent_lesson():
    service, hindsight_sdk, groq_sdk = make_service(memories=[])

    result = service.learn_from_outcome(deal_id="deal-1", outcome="lost")

    assert result.insufficient_evidence is True
    assert result.lessons == []
    assert len(result.retained_memories) == 1
    assert result.retained_memories[0].memory_type == MemoryType.DEAL_OUTCOME
    hindsight_sdk.recall_memory.assert_called_once()
    hindsight_sdk.retain_memory.assert_called_once()
    groq_sdk.chat.completions.create.assert_not_called()


def test_model_can_report_insufficient_evidence_without_storing_a_lesson():
    draft = OutcomeLearningDraft(
        observed_facts=[
            ObservedOutcomeFact(
                statement="A pricing discussion occurred.",
                supporting_memory_ids=["security-1"],
            )
        ],
        insufficient_evidence=True,
        insufficient_reason="The history does not explain the final outcome.",
    )
    service, hindsight_sdk, _ = make_service(draft=draft)

    result = service.learn_from_outcome(deal_id="deal-1", outcome="stalled")

    assert result.insufficient_evidence is True
    assert result.message == "The history does not explain the final outcome."
    assert result.lessons == []
    assert len(result.retained_memories) == 1
    hindsight_sdk.retain_memory.assert_called_once()


def test_conflicting_memories_are_preserved_as_observed_facts():
    memories = [
        deal_memory("security-1", "The CTO said security approval was complete."),
        deal_memory("security-2", "A later note says security approval is still pending."),
    ]
    draft = OutcomeLearningDraft(
        observed_facts=[
            ObservedOutcomeFact(
                statement="An earlier note says approval was complete.",
                supporting_memory_ids=["security-1"],
            ),
            ObservedOutcomeFact(
                statement="A later note says approval is still pending.",
                supporting_memory_ids=["security-2"],
            ),
        ],
        lessons=[
            OutcomeLesson(
                content="The deal history contains conflicting security-approval updates; verify the current status early.",
                evidence_basis="inferred",
                supporting_memory_ids=["security-1", "security-2"],
            )
        ],
    )
    service, _, _ = make_service(memories=memories, draft=draft)

    result = service.learn_from_outcome(deal_id="deal-1", outcome="stalled")

    assert len(result.observed_facts) == 2
    assert {memory_id for fact in result.observed_facts for memory_id in fact.supporting_memory_ids} == {
        "security-1",
        "security-2",
    }
    assert "conflicting" in result.lessons[0].content


def test_causal_lesson_is_rejected_without_explicit_causal_source_evidence():
    draft = OutcomeLearningDraft(
        lessons=[
            OutcomeLesson(
                content="Unresolved security concerns caused the loss.",
                evidence_basis="inferred",
                supporting_memory_ids=["security-1"],
            )
        ]
    )
    service, hindsight_sdk, _ = make_service(draft=draft)

    with pytest.raises(OutcomeLearningError, match="explicit causal evidence"):
        service.learn_from_outcome(deal_id="deal-1", outcome="lost")

    # The recorded outcome is retained, but the unsupported lesson is not.
    assert hindsight_sdk.retain_memory.call_count == 1
    assert hindsight_sdk.retain_memory.call_args.kwargs["metadata"]["memory_type"] == "deal_outcome"


def test_explicit_causal_source_can_support_a_causal_lesson():
    memories = [
        deal_memory(
            "cause-1",
            "The buyer stated the unresolved security review was the reason for the loss.",
        )
    ]
    draft = OutcomeLearningDraft(
        lessons=[
            OutcomeLesson(
                content="The unresolved security review was the reason for the loss.",
                evidence_basis="observed",
                supporting_memory_ids=["cause-1"],
                causal_claim=True,
                causal_memory_ids=["cause-1"],
            )
        ]
    )
    service, _, _ = make_service(memories=memories, draft=draft)

    result = service.learn_from_outcome(deal_id="deal-1", outcome="lost")

    assert result.lessons[0].causal_claim is True


def test_another_deals_memories_are_filtered_before_groq():
    service, _, groq_sdk = make_service(
        memories=[deal_memory("other-1", "OtherCo had a security issue.", deal_id="other-deal")]
    )

    result = service.learn_from_outcome(deal_id="deal-1", outcome="lost")

    assert result.insufficient_evidence is True
    groq_sdk.chat.completions.create.assert_not_called()
    assert result.retained_memories[0].supporting_memory_ids == []


def test_hindsight_retain_failure_is_reported():
    service, hindsight_sdk, _ = make_service()
    hindsight_sdk.retain_memory.side_effect = HindsightMemoryClientError("offline")

    with pytest.raises(OutcomeLearningError, match="retain failed"):
        service.learn_from_outcome(deal_id="deal-1", outcome="won")
