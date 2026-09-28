"""Mocked FastAPI tests; no Groq or Hindsight calls are made."""

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app as api
from Hindsight.ai.extraction import SalesIntelligenceExtraction
from Hindsight.memory.memory_schema import DealMemory, MemoryType


client = TestClient(api.app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_interaction_ingestion_uses_existing_workflow(monkeypatch):
    memory = DealMemory(
        deal_id="deal-1",
        memory_type=MemoryType.OBJECTION,
        content="Security review is pending.",
        interaction_date=datetime(2026, 9, 28, tzinfo=timezone.utc),
    )
    expected = SimpleNamespace(
        extraction=SalesIntelligenceExtraction(),
        memories=(memory,),
        retain_responses=(object(),),
    )
    calls = {}

    def fake_process(**kwargs):
        calls.update(kwargs)
        return expected

    monkeypatch.setattr(api, "process_sales_interaction", fake_process)

    response = client.post(
        "/api/deals/deal-1/interactions",
        json={
            "notes": "Security review is pending.",
            "interaction_date": "2026-09-28T10:00:00Z",
            "source": "call",
            "interaction_id": "meeting-1",
            "company": "TechNova",
            "stakeholder": "CTO",
        },
    )

    assert response.status_code == 200
    assert response.json()["deal_id"] == "deal-1"
    assert response.json()["retained_memory_count"] == 1
    assert calls["customer_company"] == "TechNova"
    assert calls["interaction_source"] == "call"


class FakeBrief:
    def generate(self, deal_id):
        return {"deal_id": deal_id, "kind": "brief"}


class FakeChanges:
    def analyze(self, deal_id):
        return {"deal_id": deal_id, "kind": "changes"}


class FakeSimilar:
    def find_similar_deals(self, deal_id):
        return {"current_deal_id": deal_id, "kind": "similar"}


class FakeWhy:
    def explain(self, deal_id, action):
        return {"deal_id": deal_id, "recommended_action": action}


class FakeOutcome:
    def learn_from_outcome(self, **kwargs):
        return {"deal_id": kwargs["deal_id"], "outcome": kwargs["outcome"]}


class FakeAutopsy:
    def analyze(self, deal_id, outcome):
        return {"deal_id": deal_id, "outcome": outcome}


def test_brief_endpoint(monkeypatch):
    monkeypatch.setattr(api, "DealBriefGenerator", lambda: FakeBrief())
    response = client.get("/api/deals/deal-1/brief")
    assert response.status_code == 200
    assert response.json()["kind"] == "brief"


def test_changes_endpoint(monkeypatch):
    monkeypatch.setattr(api, "DealChangeAnalyzer", lambda: FakeChanges())
    response = client.get("/api/deals/deal-1/changes")
    assert response.status_code == 200
    assert response.json()["kind"] == "changes"


def test_similar_endpoint(monkeypatch):
    monkeypatch.setattr(api, "SimilarDealsFinder", lambda: FakeSimilar())
    response = client.get("/api/deals/deal-1/similar")
    assert response.status_code == 200
    assert response.json()["kind"] == "similar"


def test_why_endpoint(monkeypatch):
    monkeypatch.setattr(api, "RecommendationExplainer", lambda: FakeWhy())
    response = client.post(
        "/api/deals/deal-1/why", json={"action": "send security documentation"}
    )
    assert response.status_code == 200
    assert response.json()["recommended_action"] == "send security documentation"


def test_outcome_endpoint(monkeypatch):
    fake = FakeOutcome()
    monkeypatch.setattr(api, "OutcomeLearningService", lambda: fake)
    response = client.post(
        "/api/deals/deal-1/outcome",
        json={"outcome": "lost", "company": "TechNova"},
    )
    assert response.status_code == 200
    assert response.json() == {"deal_id": "deal-1", "outcome": "lost"}


def test_autopsy_endpoint(monkeypatch):
    monkeypatch.setattr(api, "DealAutopsyAnalyzer", lambda: FakeAutopsy())
    response = client.post(
        "/api/deals/deal-1/autopsy", json={"outcome": "stalled"}
    )
    assert response.status_code == 200
    assert response.json() == {"deal_id": "deal-1", "outcome": "stalled"}


def test_invalid_input_returns_422_without_calling_services(monkeypatch):
    process = lambda **kwargs: (_ for _ in ()).throw(AssertionError("called"))
    monkeypatch.setattr(api, "process_sales_interaction", process)

    response = client.post("/api/deals/deal-1/interactions", json={"notes": ""})

    assert response.status_code == 422

