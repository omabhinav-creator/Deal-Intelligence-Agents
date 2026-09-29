"""Mocked tests for deal-specific, evidence-backed Deal Brief generation."""

import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
import httpx
from groq import Groq, RateLimitError

from backend.memory.hindsight_client import (
    HindsightMemoryClient,
    HindsightMemoryClientError,
)
from Hindsight.ai.deal_brief import (
    BriefFact,
    BriefRecommendation,
    DealBriefDraft,
    DealBriefError,
    DealBriefGenerator,
    DealBriefRateLimitError,
    _retry_after_seconds,
)


def recalled_memory(
    memory_id: str,
    text: str,
    *,
    deal_id: str,
    memory_type: str,
    stakeholder_name: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=memory_id,
        text=text,
        type="world",
        metadata={
            "deal_id": deal_id,
            "memory_type": memory_type,
            "customer_name": "TechNova",
            "stakeholder_name": stakeholder_name,
        },
        tags=[f"deal:{deal_id}", f"type:{memory_type}"],
        occurred_start="2026-09-28T12:00:00Z",
        mentioned_at=None,
    )


def make_groq_client(draft: DealBriefDraft) -> tuple[Groq, Mock]:
    client = Mock()
    message = SimpleNamespace(content=draft.model_dump_json(), refusal=None)
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=message)]
    )
    return cast(Groq, client), client


def rate_limit_error(retry_after: str | None = None) -> RateLimitError:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, headers=headers, request=request)
    return RateLimitError(
        "Error code: 429 - provider quota exhausted",
        response=response,
        body={"error": {"message": "provider quota exhausted"}},
    )


def sample_draft() -> DealBriefDraft:
    return DealBriefDraft(
        customer_company="TechNova",
        customer_summary=BriefFact(
            statement="TechNova is evaluating the product for an ERP-integrated deployment.",
            evidence_ids=["memory-1"],
        ),
        current_deal_status=BriefFact(
            statement="The deal is still under evaluation.",
            evidence_ids=["memory-2"],
        ),
        key_stakeholders=[
            BriefFact(
                statement="The CTO is a technical stakeholder.",
                evidence_ids=["memory-1"],
            ),
            BriefFact(
                statement="Sarah is in procurement.",
                evidence_ids=["memory-3"],
            ),
        ],
        stakeholder_concerns=[
            BriefFact(
                statement="The CTO is concerned about ERP integration.",
                evidence_ids=["memory-1"],
            )
        ],
        main_objections=[
            BriefFact(
                statement="ERP integration is an objection to resolve.",
                evidence_ids=["memory-1"],
            )
        ],
        competitors=[
            BriefFact(
                statement="TechNova is evaluating CompetitorX.",
                evidence_ids=["memory-2"],
            )
        ],
        pricing_discussions=[
            BriefFact(
                statement="Procurement asked about reducing the annual price.",
                evidence_ids=["memory-3"],
            )
        ],
        customer_requirements=[],
        previous_commitments=[
            BriefFact(
                statement="The team committed to send integration details.",
                evidence_ids=["memory-1"],
            )
        ],
        recent_developments=[
            BriefFact(
                statement="CompetitorX is being actively evaluated.",
                evidence_ids=["memory-2"],
            )
        ],
        recommended_preparation=[
            BriefRecommendation(
                action="Prepare an ERP integration overview.",
                rationale="It addresses the CTO's recorded concern.",
                evidence_ids=["memory-1"],
            ),
            BriefRecommendation(
                action="Review pricing flexibility before the meeting.",
                rationale="Procurement asked about the annual price.",
                evidence_ids=["memory-3"],
            ),
        ],
        insufficient_information=False,
    )


def test_deal_with_memories_generates_brief_and_returns_supporting_evidence():
    memories = [
        recalled_memory(
            "memory-1",
            "TechNova's CTO is concerned about ERP integration.",
            deal_id="technova-deal",
            memory_type="stakeholder_concern",
            stakeholder_name="CTO",
        ),
        recalled_memory(
            "memory-2",
            "TechNova is evaluating CompetitorX.",
            deal_id="technova-deal",
            memory_type="competitor",
        ),
        recalled_memory(
            "memory-3",
            "Sarah from procurement asked whether the annual price can be reduced.",
            deal_id="technova-deal",
            memory_type="pricing_discussion",
            stakeholder_name="Sarah",
        ),
    ]
    memory_client = Mock(spec=HindsightMemoryClient)
    memory_client.recall_memory.return_value = SimpleNamespace(results=memories)
    groq_client, _ = make_groq_client(sample_draft())
    generator = DealBriefGenerator(
        memory_client=cast(HindsightMemoryClient, memory_client),
        groq_client=groq_client,
        model="mock-model",
    )

    brief = generator.generate("technova-deal")

    assert brief.customer_company == "TechNova"
    assert "ERP integration" in brief.stakeholder_concerns[0].statement
    assert "CompetitorX" in brief.competitors[0].statement
    assert "annual price" in brief.pricing_discussions[0].statement
    assert brief.recommended_preparation
    assert {evidence.memory_id for evidence in brief.supporting_evidence} == {
        "memory-1",
        "memory-2",
        "memory-3",
    }
    assert brief.supporting_evidence[0].content == memories[0].text


def test_brief_accepts_groq_messages_without_optional_refusal_field():
    memory = recalled_memory(
        "memory-1",
        "TechNova is evaluating the product.",
        deal_id="technova-deal",
        memory_type="important_fact",
    )
    memory_client = Mock(spec=HindsightMemoryClient)
    memory_client.recall_memory.return_value = SimpleNamespace(results=[memory])
    groq_client = Mock()
    groq_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=DealBriefDraft().model_dump_json()
        ))]
    )
    generator = DealBriefGenerator(
        memory_client=cast(HindsightMemoryClient, memory_client),
        groq_client=cast(Groq, groq_client),
    )

    brief = generator.generate("technova-deal")

    assert brief.deal_id == "technova-deal"
    assert brief.supporting_evidence[0].memory_id == "memory-1"


def test_recall_uses_requested_deal_id_and_llm_never_receives_other_deals():
    matching_memory = recalled_memory(
        "memory-1",
        "TechNova is evaluating CompetitorX.",
        deal_id="technova-deal",
        memory_type="competitor",
    )
    unrelated_memory = recalled_memory(
        "other-memory",
        "OtherCo has a confidential renewal risk.",
        deal_id="other-deal",
        memory_type="risk",
    )
    memory_client = Mock(spec=HindsightMemoryClient)
    memory_client.recall_memory.return_value = SimpleNamespace(
        results=[matching_memory, unrelated_memory]
    )
    groq_client, groq_mock = make_groq_client(
        DealBriefDraft(
            competitors=[
                BriefFact(
                    statement="TechNova is evaluating CompetitorX.",
                    evidence_ids=["memory-1"],
                )
            ]
        )
    )
    generator = DealBriefGenerator(
        memory_client=cast(HindsightMemoryClient, memory_client),
        groq_client=groq_client,
    )

    generator.generate("technova-deal")

    recall_args = memory_client.recall_memory.call_args
    assert recall_args.args[0].find("technova-deal") >= 0
    assert recall_args.kwargs["tags"] == ["deal:technova-deal"]
    llm_payload = json.loads(groq_mock.chat.completions.create.call_args.kwargs["messages"][1]["content"])
    serialized_memories = json.dumps(llm_payload["supporting_memories"])
    assert "OtherCo" not in serialized_memories
    assert "other-memory" not in serialized_memories
    assert len(llm_payload["supporting_memories"]) == 1


def test_empty_memory_result_returns_insufficient_brief_without_groq_call():
    memory_client = Mock(spec=HindsightMemoryClient)
    memory_client.recall_memory.return_value = SimpleNamespace(results=[])
    groq_client, groq_mock = make_groq_client(DealBriefDraft())
    generator = DealBriefGenerator(
        memory_client=cast(HindsightMemoryClient, memory_client),
        groq_client=groq_client,
    )

    brief = generator.generate("unknown-deal")

    assert brief.deal_id == "unknown-deal"
    assert brief.insufficient_information is True
    assert brief.supporting_evidence == []
    assert brief.recommended_preparation == []
    groq_mock.chat.completions.create.assert_not_called()


def test_every_claim_must_cite_a_returned_memory():
    memory = recalled_memory(
        "memory-1",
        "TechNova is evaluating CompetitorX.",
        deal_id="technova-deal",
        memory_type="competitor",
    )
    memory_client = Mock(spec=HindsightMemoryClient)
    memory_client.recall_memory.return_value = SimpleNamespace(results=[memory])
    groq_client, _ = make_groq_client(
        DealBriefDraft(
            competitors=[
                BriefFact(
                    statement="An unsupported claim.",
                    evidence_ids=["not-returned-by-hindsight"],
                )
            ]
        )
    )
    generator = DealBriefGenerator(
        memory_client=cast(HindsightMemoryClient, memory_client),
        groq_client=groq_client,
    )

    with pytest.raises(DealBriefError, match="not returned by Hindsight"):
        generator.generate("technova-deal")


def test_recall_failure_is_reported_without_groq_call():
    memory_client = Mock(spec=HindsightMemoryClient)
    memory_client.recall_memory.side_effect = HindsightMemoryClientError("offline")
    groq_client, groq_mock = make_groq_client(DealBriefDraft())
    generator = DealBriefGenerator(
        memory_client=cast(HindsightMemoryClient, memory_client),
        groq_client=groq_client,
    )

    with pytest.raises(DealBriefError, match="Hindsight memory recall failed"):
        generator.generate("technova-deal")
    groq_mock.chat.completions.create.assert_not_called()


def test_groq_429_without_retry_after_is_returned_without_retry_or_sleep(monkeypatch):
    memory = recalled_memory(
        "memory-1",
        "TechNova requested a security review.",
        deal_id="technova-deal",
        memory_type="important_fact",
    )
    memory_client = Mock(spec=HindsightMemoryClient)
    memory_client.recall_memory.return_value = SimpleNamespace(results=[memory])
    groq_client, groq_mock = make_groq_client(DealBriefDraft())
    groq_mock.chat.completions.create.side_effect = rate_limit_error()
    generator = DealBriefGenerator(
        memory_client=cast(HindsightMemoryClient, memory_client),
        groq_client=groq_client,
    )
    sleep = Mock()
    monkeypatch.setattr("Hindsight.ai.deal_brief.time.sleep", sleep)

    with pytest.raises(DealBriefRateLimitError, match="HTTP 429") as error:
        generator.generate("technova-deal")

    assert "provider quota exhausted" in error.value.provider_message
    assert error.value.retry_after is None
    assert groq_mock.chat.completions.create.call_count == 1
    sleep.assert_not_called()


def test_groq_retry_after_allows_only_one_bounded_retry(monkeypatch):
    memory = recalled_memory(
        "memory-1",
        "TechNova requested a security review.",
        deal_id="technova-deal",
        memory_type="important_fact",
    )
    memory_client = Mock(spec=HindsightMemoryClient)
    memory_client.recall_memory.return_value = SimpleNamespace(results=[memory])
    groq_client, groq_mock = make_groq_client(DealBriefDraft())
    groq_mock.chat.completions.create.side_effect = [
        rate_limit_error("2"),
        rate_limit_error("30"),
    ]
    generator = DealBriefGenerator(
        memory_client=cast(HindsightMemoryClient, memory_client),
        groq_client=groq_client,
    )
    sleep = Mock()
    monkeypatch.setattr("Hindsight.ai.deal_brief.time.sleep", sleep)

    with pytest.raises(DealBriefRateLimitError) as error:
        generator.generate("technova-deal")

    assert error.value.retry_after == "30"
    assert groq_mock.chat.completions.create.call_count == 2
    sleep.assert_called_once_with(2.0)


def test_groq_long_retry_after_is_preserved_without_waiting_or_retrying(monkeypatch):
    memory = recalled_memory(
        "memory-1",
        "TechNova requested a security review.",
        deal_id="technova-deal",
        memory_type="important_fact",
    )
    memory_client = Mock(spec=HindsightMemoryClient)
    memory_client.recall_memory.return_value = SimpleNamespace(results=[memory])
    groq_client, groq_mock = make_groq_client(DealBriefDraft())
    groq_mock.chat.completions.create.side_effect = rate_limit_error("60")
    generator = DealBriefGenerator(
        memory_client=cast(HindsightMemoryClient, memory_client),
        groq_client=groq_client,
    )
    sleep = Mock()
    monkeypatch.setattr("Hindsight.ai.deal_brief.time.sleep", sleep)

    with pytest.raises(DealBriefRateLimitError) as error:
        generator.generate("technova-deal")

    assert error.value.retry_after == "60"
    assert groq_mock.chat.completions.create.call_count == 1
    sleep.assert_not_called()


def test_groq_retry_after_short_retry_can_succeed_with_validated_real_shape(monkeypatch):
    memories = [
        recalled_memory(
            "memory-1",
            "TechNova is evaluating CompetitorX.",
            deal_id="technova-deal",
            memory_type="competitor",
        ),
        recalled_memory(
            "memory-2",
            "The CTO requested an integration overview.",
            deal_id="technova-deal",
            memory_type="important_fact",
        ),
        recalled_memory(
            "memory-3",
            "Procurement asked whether the price can be reduced.",
            deal_id="technova-deal",
            memory_type="pricing_discussion",
        ),
    ]
    memory_client = Mock(spec=HindsightMemoryClient)
    memory_client.recall_memory.return_value = SimpleNamespace(results=memories)
    groq_client, groq_mock = make_groq_client(sample_draft())
    success_response = groq_mock.chat.completions.create.return_value
    groq_mock.chat.completions.create.side_effect = [rate_limit_error("1"), success_response]
    generator = DealBriefGenerator(
        memory_client=cast(HindsightMemoryClient, memory_client),
        groq_client=groq_client,
    )
    sleep = Mock()
    monkeypatch.setattr("Hindsight.ai.deal_brief.time.sleep", sleep)

    brief = generator.generate("technova-deal")

    assert brief.customer_company == "TechNova"
    assert len(brief.supporting_evidence) == 3
    assert groq_mock.chat.completions.create.call_count == 2
    sleep.assert_called_once_with(1.0)


def test_retry_after_parser_accepts_seconds_and_http_date():
    future = datetime.now(timezone.utc) + timedelta(seconds=3)

    assert _retry_after_seconds("2.5") == 2.5
    assert _retry_after_seconds(format_datetime(future, usegmt=True)) <= 3
    assert _retry_after_seconds("not-a-retry-date") is None
