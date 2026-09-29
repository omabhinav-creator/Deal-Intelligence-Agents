"""Seed small, labeled learning examples through the real DealMind services."""

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from bson import ObjectId

from backend.database import _get_database, close_database_client
from backend.memory.hindsight_client import HindsightMemoryClient
from Hindsight.ai.agent import process_sales_interaction
from Hindsight.ai.extraction import (
    ExtractedFact,
    ExtractedStakeholder,
    SalesIntelligenceExtraction,
)
from Hindsight.memory.memory_schema import DealMemory, MemoryType
from Hindsight.memory.learning import OutcomeLearningService
from Hindsight.memory.retain import retain_deal_memory


DEMO_LEARNING_CASES = (
    {
        "company_name": "TechNova",
        "outcome": "won",
        "interaction_id": "demo-learning-technova-won",
        "notes": (
            "TechNova's CTO and VP of Operations approved the integration plan after "
            "the team completed the security review and mapped the API rollout to a "
            "measurable reduction in manual reconciliation. The executive sponsor "
            "confirmed budget and asked for a final implementation timeline."
        ),
        "extraction": {
            "stakeholders": [("Maya Chen", "CTO"), ("Ravi Shah", "VP of Operations")],
            "customer_requirements": ["API rollout mapped to reconciliation workflow"],
            "important_facts": ["Security review completed before final approval"],
            "buying_signals": ["Executive sponsor confirmed budget"],
            "commitments": ["Customer requested the implementation timeline"],
        },
    },
    {
        "company_name": "Acme Corp",
        "outcome": "won",
        "interaction_id": "demo-learning-acme-won",
        "notes": (
            "Acme Corp's revenue operations director endorsed the proposal after a "
            "focused workflow demonstration and a quantified forecast of faster "
            "quote turnaround. Procurement accepted the commercial terms and the "
            "CFO approved the purchase for the next quarter."
        ),
        "extraction": {
            "stakeholders": [("Elena Brooks", "Revenue Operations Director"), ("Jon Bell", "CFO")],
            "customer_requirements": ["Faster quote turnaround workflow"],
            "important_facts": ["Proposal included a quantified business case"],
            "buying_signals": ["Procurement accepted the commercial terms"],
            "commitments": ["Purchase approved for the next quarter"],
        },
    },
    {
        "company_name": "Nova Systems",
        "outcome": "lost",
        "interaction_id": "demo-learning-nova-lost",
        "notes": (
            "Nova Systems' sourcing manager said the annual subscription was above "
            "the approved budget and requested a materially lower price. The finance "
            "review was delayed while a lower-cost competitor was evaluated, and the "
            "champion could not secure an exception before the buying window closed."
        ),
        "extraction": {
            "stakeholders": [("Priya Nair", "Sourcing Manager")],
            "pricing_information": ["Annual subscription was above the approved budget"],
            "objections": ["Customer requested a materially lower price"],
            "competitors": ["A lower-cost competitor was evaluated"],
            "risks": ["Finance review was delayed"],
            "unresolved_questions": ["Champion could not secure a budget exception"],
        },
    },
    {
        "company_name": "Quantum Systems",
        "outcome": "lost",
        "interaction_id": "demo-learning-quantum-lost",
        "notes": (
            "Quantum Systems' IT lead raised unresolved data-residency questions and "
            "the legal review missed two decision meetings. The buying committee "
            "ultimately selected a competitor that already had the required regional "
            "hosting certification, despite positive feedback from the operations team."
        ),
        "extraction": {
            "stakeholders": [("Marcus Lee", "IT Lead"), ("Sofia Ruiz", "Legal Counsel")],
            "customer_requirements": ["Regional hosting certification"],
            "stakeholder_concerns": ["Data-residency questions remained unresolved"],
            "competitors": ["Competitor already had the required certification"],
            "risks": ["Legal review missed two decision meetings"],
            "unresolved_questions": ["Data-residency requirements were not cleared"],
        },
    },
)


class DemoExtractor:
    """Deterministic extractor used only for labeled demo seed records."""

    def __init__(self, case: dict[str, object]):
        self.case = case

    def extract(self, _meeting_notes: str) -> SalesIntelligenceExtraction:
        facts = self.case["extraction"]

        def extracted(items: list[str]) -> list[ExtractedFact]:
            return [ExtractedFact(content=item) for item in items]

        return SalesIntelligenceExtraction(
            customer_company=self.case["company_name"],
            stakeholders=[
                ExtractedStakeholder(name=name, role=role)
                for name, role in facts.get("stakeholders", [])
            ],
            stakeholder_concerns=extracted(facts.get("stakeholder_concerns", [])),
            objections=extracted(facts.get("objections", [])),
            competitors=extracted(facts.get("competitors", [])),
            pricing_information=extracted(facts.get("pricing_information", [])),
            customer_requirements=extracted(facts.get("customer_requirements", [])),
            commitments=extracted(facts.get("commitments", [])),
            important_facts=extracted(facts.get("important_facts", [])),
            risks=extracted(facts.get("risks", [])),
            buying_signals=extracted(facts.get("buying_signals", [])),
            unresolved_questions=extracted(facts.get("unresolved_questions", [])),
        )


class DemoOutcomeClient:
    """Return evidence-linked demo analysis through OutcomeLearningService."""

    def __init__(self, outcome: str):
        self.outcome = outcome
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, *, messages, **_kwargs):
        request = json.loads(messages[-1]["content"])
        evidence = request["deal_memories"]
        supporting_ids = [item["memory_id"] for item in evidence[:2]]
        lesson = (
            "A quantified business case and confirmed executive sponsorship were present "
            "in this successful outcome."
            if self.outcome == "won"
            else "Budget or unresolved approval requirements remained open in this unsuccessful outcome."
        )
        content = json.dumps({
            "observed_facts": [
                {
                    "statement": item["content"],
                    "supporting_memory_ids": [item["memory_id"]],
                }
                for item in evidence[:2]
            ],
            "lessons": [{
                "content": lesson,
                "evidence_basis": "inferred",
                "supporting_memory_ids": supporting_ids,
                "causal_claim": False,
                "causal_memory_ids": [],
            }],
            "insufficient_evidence": False,
        })
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content, refusal=None))]
        )


def _retain_explicit_outcome(
    client: HindsightMemoryClient,
    *,
    deal_id: str,
    company_name: str,
    outcome: str,
    interaction_id: str,
    outcome_date: datetime,
) -> None:
    memory = DealMemory(
        deal_id=deal_id,
        memory_type=MemoryType.DEAL_OUTCOME,
        content=f"{company_name} deal outcome recorded as {outcome}.",
        customer_name=company_name,
        interaction_id=interaction_id,
        interaction_date=outcome_date,
        interaction_source="DealMind labeled demo learning data",
        status=outcome,
        evidence_basis="observed",
    )
    retain_deal_memory(
        memory,
        client,
        document_id=f"{interaction_id}:demo-outcome",
    )


async def _deal_ids_by_company(db) -> dict[str, str]:
    names = [case["company_name"] for case in DEMO_LEARNING_CASES]
    documents = await db["deals"].find(
        {"company_name": {"$in": names}},
        {"company_name": 1},
    ).to_list(length=len(names))
    deal_ids = {document["company_name"]: str(document["_id"]) for document in documents}
    missing = [name for name in names if name not in deal_ids]
    if missing:
        raise RuntimeError(f"Required seeded deals are missing: {', '.join(missing)}")
    return deal_ids


async def _update_deal_statuses(updates: list[tuple[str, str, datetime]]) -> None:
    db = _get_database()
    for deal_id, outcome, updated_at in updates:
        await db["deals"].update_one(
            {"_id": ObjectId(deal_id)},
            {"$set": {"status": outcome, "updated_at": updated_at}},
        )


def _seeded_memory_state(
    client: HindsightMemoryClient,
    deal_id: str,
    interaction_id: str,
) -> tuple[bool, bool, bool]:
    recalled = client.recall_memory(
        f"Retrieve the recorded outcome for deal {deal_id}.",
        tags=[f"deal:{deal_id}"],
        max_tokens=4096,
    )
    matching = [
        memory
        for memory in recalled.results
        if (memory.metadata or {}).get("interaction_id") == interaction_id
    ]
    has_interaction = any(
        (memory.metadata or {}).get("memory_type") not in {"deal_outcome", "lesson_learned"}
        for memory in matching
    )
    has_outcome = any(
        (memory.metadata or {}).get("memory_type") == "deal_outcome"
        for memory in matching
    )
    has_lesson = any(
        (memory.metadata or {}).get("memory_type") == "lesson_learned"
        for memory in matching
    )
    return has_interaction, has_outcome, has_lesson


def seed_demo_learning() -> dict[str, str]:
    """Retain demo interactions and learn outcomes without inventing memory IDs."""
    db = _get_database()
    deal_ids = asyncio.run(_deal_ids_by_company(db))
    close_database_client()
    client = HindsightMemoryClient()
    results: dict[str, str] = {}
    status_updates: list[tuple[str, str, datetime]] = []
    try:
        for case in DEMO_LEARNING_CASES:
            deal_id = deal_ids[case["company_name"]]
            interaction_date = datetime.now(timezone.utc)
            has_interaction, has_outcome, has_lesson = _seeded_memory_state(
                client, deal_id, case["interaction_id"]
            )
            if has_lesson:
                _retain_explicit_outcome(
                    client,
                    deal_id=deal_id,
                    company_name=case["company_name"],
                    outcome=case["outcome"],
                    interaction_id=case["interaction_id"],
                    outcome_date=interaction_date,
                )
                status_updates.append((deal_id, case["outcome"], interaction_date))
                results[case["company_name"]] = "already seeded"
                continue
            interaction_count = 0
            if not has_interaction:
                interaction = process_sales_interaction(
                    deal_id=deal_id,
                    meeting_notes=case["notes"],
                    customer_company=case["company_name"],
                    interaction_date=interaction_date,
                    interaction_id=case["interaction_id"],
                    interaction_source="DealMind labeled demo learning data",
                    extractor=DemoExtractor(case),
                    memory_client=client,
                )
                interaction_count = len(interaction.retain_responses)
            learner = OutcomeLearningService(
                memory_client=client,
                groq_client=DemoOutcomeClient(case["outcome"]),
            )
            learned = learner.learn_from_outcome(
                deal_id=deal_id,
                outcome=case["outcome"],
                customer_name=case["company_name"],
                outcome_date=interaction_date,
                interaction_id=case["interaction_id"],
            )
            _retain_explicit_outcome(
                client,
                deal_id=deal_id,
                company_name=case["company_name"],
                outcome=case["outcome"],
                interaction_id=case["interaction_id"],
                outcome_date=interaction_date,
            )
            status_updates.append((deal_id, case["outcome"], interaction_date))
            results[case["company_name"]] = (
                f"{case['outcome']}: retained {interaction_count} interaction "
                f"memories and {len(learned.retained_memories)} outcome/lesson memories"
            )
    finally:
        client.close()
        close_database_client()
    asyncio.run(_update_deal_statuses(status_updates))
    close_database_client()
    return results


if __name__ == "__main__":
    for company, result in seed_demo_learning().items():
        print(f"{company}: {result}")
