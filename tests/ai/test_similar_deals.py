"""Mocked Similar Deals tests using synthetic deal memories."""

import json
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
from groq import Groq

from backend.memory.hindsight_client import HindsightMemoryClient
from Hindsight.ai.deal_brief import BriefEvidence
from Hindsight.ai.deal_changes import ChangeCategory, ChangeType, EvidenceBasis
from Hindsight.ai.similar_deals import (
    HistoricalDealFact,
    MatchingCharacteristic,
    SimilarDealDraft,
    SimilarDealsAnalysis,
    SimilarDealsDraft,
    SimilarDealsError,
    SimilarDealsFinder,
)

CURRENT_DEAL = "technova-deal"


def recalled_memory(
    memory_id: str,
    deal_id: str,
    content: str,
    *,
    memory_type: str = "important_fact",
    date: str | None = "2026-09-01T10:00:00Z",
    company: str | None = None,
) -> SimpleNamespace:
    metadata = {
        "deal_id": deal_id,
        "memory_type": memory_type,
        "interaction_source": "discovery meeting",
    }
    if company is not None:
        metadata["customer_name"] = company
    if date is not None:
        metadata["interaction_date"] = date
    return SimpleNamespace(
        id=memory_id,
        text=content,
        type="world",
        metadata=metadata,
        tags=[f"deal:{deal_id}", f"type:{memory_type}"],
        occurred_start=date,
        mentioned_at=None,
        document_id=f"meeting-{memory_id}",
    )


def high_similarity_draft() -> SimilarDealsDraft:
    return SimilarDealsDraft(
        deals=[
            SimilarDealDraft(
                historical_deal_id="datasphere-deal",
                is_similar=True,
                similarity_reason=(
                    "Both deals involve ERP integration concerns and procurement pricing discussions."
                ),
                reason_memory_ids=["current-erp", "old-erp", "old-price"],
                matching_characteristics=[
                    MatchingCharacteristic(
                        characteristic="ERP integration concern",
                        evidence_basis=EvidenceBasis.OBSERVED,
                        current_memory_ids=["current-erp"],
                        historical_memory_ids=["old-erp"],
                    ),
                    MatchingCharacteristic(
                        characteristic="Procurement requested annual pricing flexibility",
                        evidence_basis=EvidenceBasis.INFERRED,
                        current_memory_ids=["current-price"],
                        historical_memory_ids=["old-price"],
                    ),
                ],
                historical_outcome=HistoricalDealFact(
                    statement="DataSphere closed after an integration pilot.",
                    memory_ids=["old-outcome"],
                ),
                useful_lesson=HistoricalDealFact(
                    statement="A technical pilot helped resolve integration concerns.",
                    memory_ids=["old-lesson"],
                ),
            )
        ]
    )


def make_finder(
    current_memories: list[SimpleNamespace],
    historical_memories: list[SimpleNamespace],
    draft: SimilarDealsDraft | None = None,
) -> tuple[SimilarDealsFinder, Mock, Mock]:
    memory_client = Mock(spec=HindsightMemoryClient)
    memory_client.recall_memory.side_effect = [
        SimpleNamespace(results=current_memories),
        SimpleNamespace(results=historical_memories),
    ]
    groq_mock = Mock()
    groq_mock.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(draft or high_similarity_draft()).model_dump_json(),
                    refusal=None,
                )
            )
        ]
    )
    finder = SimilarDealsFinder(
        memory_client=cast(HindsightMemoryClient, memory_client),
        groq_client=cast(Groq, groq_mock),
        model="mock-model",
    )
    return finder, memory_client, groq_mock


def current_technova_memories() -> list[SimpleNamespace]:
    return [
        recalled_memory(
            "current-erp",
            CURRENT_DEAL,
            "TechNova's CTO is concerned about ERP integration.",
            memory_type="stakeholder_concern",
            company="TechNova",
        ),
        recalled_memory(
            "current-price",
            CURRENT_DEAL,
            "Sarah from procurement requested a lower annual price.",
            memory_type="pricing_discussion",
            company="TechNova",
            date="2026-09-05T10:00:00Z",
        ),
    ]


def historical_datasphere_memories() -> list[SimpleNamespace]:
    return [
        recalled_memory(
            "old-erp",
            "datasphere-deal",
            "DataSphere's CTO had an ERP integration concern.",
            memory_type="objection",
            company="DataSphere",
            date="2025-04-01T10:00:00Z",
        ),
        recalled_memory(
            "old-price",
            "datasphere-deal",
            "DataSphere procurement asked about annual pricing flexibility.",
            memory_type="pricing_discussion",
            company="DataSphere",
            date="2025-04-02T10:00:00Z",
        ),
        recalled_memory(
            "old-outcome",
            "datasphere-deal",
            "DataSphere closed after an integration pilot.",
            memory_type="deal_outcome",
            company="DataSphere",
            date="2025-05-01T10:00:00Z",
        ),
        recalled_memory(
            "old-lesson",
            "datasphere-deal",
            "A technical pilot helped resolve the integration concern.",
            memory_type="lesson_learned",
            company="DataSphere",
            date="2025-05-02T10:00:00Z",
        ),
    ]


def test_highly_similar_historical_deal_includes_outcome_lesson_and_evidence():
    finder, _, _ = make_finder(
        current_technova_memories(), historical_datasphere_memories()
    )

    result = finder.find_similar_deals(CURRENT_DEAL)

    assert result.insufficient_data is False
    assert len(result.similar_deals) == 1
    match = result.similar_deals[0]
    assert match.historical_deal_id == "datasphere-deal"
    assert match.company_name == "DataSphere"
    assert match.historical_outcome is not None
    assert match.useful_lesson is not None
    assert len(match.matching_characteristics) == 2
    assert {item.memory_id for item in match.current_evidence} == {
        "current-erp",
        "current-price",
    }
    assert {item.memory_id for item in match.historical_evidence} == {
        "old-erp",
        "old-price",
        "old-outcome",
        "old-lesson",
    }


def test_partially_similar_deal_returns_only_supported_matching_characteristic():
    historical = [
        recalled_memory(
            "old-erp",
            "cloudcore-deal",
            "CloudCore's team asked about ERP integration.",
            memory_type="customer_requirement",
            company="CloudCore",
        ),
        recalled_memory(
            "old-fact",
            "cloudcore-deal",
            "CloudCore purchased a two-year contract.",
            company="CloudCore",
            date="2025-04-02T10:00:00Z",
        ),
    ]
    draft = SimilarDealsDraft(
        deals=[
            SimilarDealDraft(
                historical_deal_id="cloudcore-deal",
                is_similar=True,
                similarity_reason="Both customers raised ERP integration needs.",
                reason_memory_ids=["current-erp", "old-erp"],
                matching_characteristics=[
                    MatchingCharacteristic(
                        characteristic="ERP integration requirement",
                        evidence_basis=EvidenceBasis.OBSERVED,
                        current_memory_ids=["current-erp"],
                        historical_memory_ids=["old-erp"],
                    )
                ],
            )
        ]
    )
    finder, _, _ = make_finder(current_technova_memories(), historical, draft)

    result = finder.find_similar_deals(CURRENT_DEAL)

    assert len(result.similar_deals) == 1
    assert len(result.similar_deals[0].matching_characteristics) == 1
    assert result.similar_deals[0].historical_outcome is None
    assert result.similar_deals[0].useful_lesson is None
    assert [item.memory_id for item in result.similar_deals[0].historical_evidence] == [
        "old-erp"
    ]


def test_unrelated_historical_deal_is_not_returned_as_similar():
    unrelated = [
        recalled_memory(
            "retail-fact-1",
            "retailflow-deal",
            "RetailFlow is concerned about store inventory scanning.",
            company="RetailFlow",
        ),
        recalled_memory(
            "retail-fact-2",
            "retailflow-deal",
            "RetailFlow requested barcode scanner hardware.",
            memory_type="customer_request",
            company="RetailFlow",
            date="2025-04-02T10:00:00Z",
        ),
    ]
    draft = SimilarDealsDraft(
        deals=[
            SimilarDealDraft(
                historical_deal_id="retailflow-deal",
                is_similar=False,
            )
        ]
    )
    finder, _, _ = make_finder(current_technova_memories(), unrelated, draft)

    result = finder.find_similar_deals(CURRENT_DEAL)

    assert result.similar_deals == []
    assert result.insufficient_data is True


def test_no_historical_deals_returns_clear_insufficient_result_without_groq():
    finder, memory_client, groq_mock = make_finder(current_technova_memories(), [])

    result = finder.find_similar_deals(CURRENT_DEAL)

    assert result.insufficient_data is True
    assert result.similar_deals == []
    assert "No other historical" in (result.message or "")
    assert memory_client.recall_memory.call_count == 2
    groq_mock.chat.completions.create.assert_not_called()


def test_historical_search_query_bounds_current_memory_text():
    evidence = [
        BriefEvidence(
            memory_id=f"memory-{index}",
            content=f"fact {index} " + ("detail " * 80),
            memory_type="objection",
        )
        for index in range(20)
    ]

    query = SimilarDealsFinder._build_historical_query(CURRENT_DEAL, evidence)

    assert len(query) < 1600
    assert "Current deal facts:" in query
    assert "memory-0" not in query


def test_current_deal_is_excluded_from_historical_candidates():
    current = current_technova_memories()
    historical = [
        *current,
        *historical_datasphere_memories(),
    ]
    finder, _, groq_mock = make_finder(current, historical)

    result = finder.find_similar_deals(CURRENT_DEAL)

    assert all(item.historical_deal_id != CURRENT_DEAL for item in result.similar_deals)
    prompt_payload = json.loads(
        groq_mock.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    )
    assert CURRENT_DEAL not in prompt_payload["historical_deals"]


def test_historical_deal_without_outcome_is_returned_without_inventing_one():
    historical = [
        recalled_memory(
            "deal-fact-1",
            "finedge-deal",
            "FinEdge raised a concern about ERP integration.",
            memory_type="objection",
            company="FinEdge",
        ),
        recalled_memory(
            "deal-fact-2",
            "finedge-deal",
            "FinEdge's CTO requested an integration walkthrough.",
            memory_type="customer_request",
            company="FinEdge",
            date="2025-04-02T10:00:00Z",
        ),
    ]
    draft = SimilarDealsDraft(
        deals=[
            SimilarDealDraft(
                historical_deal_id="finedge-deal",
                is_similar=True,
                similarity_reason="Both deals include an ERP integration concern.",
                reason_memory_ids=["current-erp", "deal-fact-1"],
                matching_characteristics=[
                    MatchingCharacteristic(
                        characteristic="ERP integration concern",
                        evidence_basis=EvidenceBasis.OBSERVED,
                        current_memory_ids=["current-erp"],
                        historical_memory_ids=["deal-fact-1"],
                    )
                ],
            )
        ]
    )
    finder, _, _ = make_finder(current_technova_memories(), historical, draft)

    result = finder.find_similar_deals(CURRENT_DEAL)

    assert result.similar_deals[0].historical_outcome is None
    assert result.similar_deals[0].useful_lesson is None


def test_missing_historical_company_fields_are_safe():
    historical = [
        recalled_memory(
            "no-company-1",
            "deal-without-company",
            "ERP integration is a key requirement.",
            memory_type="customer_requirement",
            company=None,
        ),
        recalled_memory(
            "no-company-2",
            "deal-without-company",
            "The buyer has asked for an integration plan.",
            memory_type="customer_request",
            company=None,
            date="2025-04-02T10:00:00Z",
        ),
    ]
    draft = SimilarDealsDraft(
        deals=[
            SimilarDealDraft(
                historical_deal_id="deal-without-company",
                is_similar=True,
                similarity_reason="Both deals share an ERP integration requirement.",
                reason_memory_ids=["current-erp", "no-company-1"],
                matching_characteristics=[
                    MatchingCharacteristic(
                        characteristic="ERP integration requirement",
                        evidence_basis=EvidenceBasis.INFERRED,
                        current_memory_ids=["current-erp"],
                        historical_memory_ids=["no-company-1"],
                    )
                ],
            )
        ]
    )
    finder, _, _ = make_finder(current_technova_memories(), historical, draft)

    result = finder.find_similar_deals(CURRENT_DEAL)

    assert result.similar_deals[0].company_name is None
    assert result.similar_deals[0].historical_evidence[0].customer_company is None


def test_multiple_similar_historical_deals_are_returned_separately():
    datasphere = historical_datasphere_memories()
    cloudcore = [
        recalled_memory(
            "cloud-erp",
            "cloudcore-deal",
            "CloudCore's CTO is concerned about ERP integration.",
            memory_type="stakeholder_concern",
            company="CloudCore",
        ),
        recalled_memory(
            "cloud-price",
            "cloudcore-deal",
            "CloudCore procurement asked about pricing.",
            memory_type="pricing_discussion",
            company="CloudCore",
            date="2025-04-02T10:00:00Z",
        ),
    ]
    draft = SimilarDealsDraft(
        deals=[
            high_similarity_draft().deals[0],
            SimilarDealDraft(
                historical_deal_id="cloudcore-deal",
                is_similar=True,
                similarity_reason="CloudCore also raised ERP integration and pricing topics.",
                reason_memory_ids=["current-erp", "cloud-erp"],
                matching_characteristics=[
                    MatchingCharacteristic(
                        characteristic="ERP integration concern",
                        evidence_basis=EvidenceBasis.OBSERVED,
                        current_memory_ids=["current-erp"],
                        historical_memory_ids=["cloud-erp"],
                    )
                ],
            ),
        ]
    )
    finder, _, _ = make_finder(
        current_technova_memories(), [*datasphere, *cloudcore], draft
    )

    result = finder.find_similar_deals(CURRENT_DEAL)

    assert [item.historical_deal_id for item in result.similar_deals] == [
        "datasphere-deal",
        "cloudcore-deal",
    ]


def test_each_similarity_has_current_and_historical_evidence_attached():
    finder, _, _ = make_finder(
        current_technova_memories(), historical_datasphere_memories()
    )

    result: SimilarDealsAnalysis = finder.find_similar_deals(CURRENT_DEAL)

    similar = result.similar_deals[0]
    assert similar.current_evidence
    assert similar.historical_evidence
    assert set(similar.reason_memory_ids).issubset(
        {item.memory_id for item in similar.current_evidence}
        | {item.memory_id for item in similar.historical_evidence}
    )


def test_uncited_or_other_deal_evidence_is_rejected():
    draft = high_similarity_draft()
    draft.deals[0].matching_characteristics[0].historical_memory_ids = [
        "memory-from-unrecalled-deal"
    ]
    finder, _, _ = make_finder(
        current_technova_memories(), historical_datasphere_memories(), draft
    )

    with pytest.raises(SimilarDealsError, match="another deal"):
        finder.find_similar_deals(CURRENT_DEAL)
