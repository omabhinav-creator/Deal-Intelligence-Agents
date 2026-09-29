"""Mocked FastAPI tests; no Groq or Hindsight calls are made."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from backend.auth import get_current_user
from backend.main import app
from backend.routes import hindsight_intelligence as api
from Hindsight.ai.extraction import SalesIntelligenceExtraction
from Hindsight.memory.memory_schema import DealMemory, MemoryType


client = TestClient(app)


@pytest.fixture(autouse=True)
def authenticated_api_requests():
    app.dependency_overrides[get_current_user] = lambda: {"_id": "test-user"}
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_preflight_allows_only_configured_live_server_origin():
    allowed = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://127.0.0.1:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    denied = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://127.0.0.1:9999",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5500"
    assert "access-control-allow-origin" not in denied.headers


def test_memory_recall_excludes_memories_from_other_deals(monkeypatch):
    def memory(memory_id, deal_id):
        return SimpleNamespace(
            id=memory_id,
            text=f"Evidence for {deal_id}",
            type="observation",
            metadata={"deal_id": deal_id, "memory_type": "objection"},
            tags=[f"deal:{deal_id}"],
            occurred_start=None,
            mentioned_at=None,
            document_id=None,
        )

    class FakeMemoryClient:
        def recall_memory(self, *_args, **_kwargs):
            return SimpleNamespace(results=[memory("memory-a", "deal-a"), memory("memory-b", "deal-b")])

        def close(self):
            pass

    monkeypatch.setattr(api, "HindsightMemoryClient", FakeMemoryClient)

    response = client.get("/api/deals/deal-a/memories")

    assert response.status_code == 200
    assert [item["memory_id"] for item in response.json()["memories"]] == ["memory-a"]


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
        try:
            asyncio.get_running_loop()
            calls["running_in_event_loop"] = True
        except RuntimeError:
            calls["running_in_event_loop"] = False
        return expected

    class FakeInteractions:
        async def insert_one(self, document):
            calls["persisted_interaction"] = document

    class FakeDatabase:
        def __getitem__(self, name):
            assert name == "interactions"
            return FakeInteractions()

    async def fake_get_database():
        return FakeDatabase()

    monkeypatch.setattr(api, "process_sales_interaction", fake_process)
    monkeypatch.setattr(api, "get_database", fake_get_database)

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
    assert calls["running_in_event_loop"] is False
    assert calls["persisted_interaction"]["content"] == "Security review is pending."
    assert calls["persisted_interaction"]["extraction"]


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
    monkeypatch.setattr(api, "DealBriefGenerator", lambda **_kwargs: FakeBrief())
    response = client.get("/api/deals/deal-1/brief")
    assert response.status_code == 200
    assert response.json()["kind"] == "brief"


def test_changes_endpoint(monkeypatch):
    monkeypatch.setattr(api, "DealChangeAnalyzer", lambda **_kwargs: FakeChanges())
    response = client.get("/api/deals/deal-1/changes")
    assert response.status_code == 200
    assert response.json()["kind"] == "changes"


def test_similar_endpoint(monkeypatch):
    monkeypatch.setattr(api, "SimilarDealsFinder", lambda **_kwargs: FakeSimilar())
    response = client.get("/api/deals/deal-1/similar")
    assert response.status_code == 200
    assert response.json()["kind"] == "similar"


def test_why_endpoint(monkeypatch):
    monkeypatch.setattr(api, "RecommendationExplainer", lambda **_kwargs: FakeWhy())
    response = client.post(
        "/api/deals/deal-1/why", json={"action": "send security documentation"}
    )
    assert response.status_code == 200
    assert response.json()["recommended_action"] == "send security documentation"


def test_outcome_endpoint(monkeypatch):
    fake = FakeOutcome()
    monkeypatch.setattr(api, "OutcomeLearningService", lambda **_kwargs: fake)
    response = client.post(
        "/api/deals/deal-1/outcome",
        json={"outcome": "lost", "company": "TechNova"},
    )
    assert response.status_code == 200
    assert response.json() == {"deal_id": "deal-1", "outcome": "lost"}


def test_autopsy_endpoint(monkeypatch):
    monkeypatch.setattr(api, "DealAutopsyAnalyzer", lambda **_kwargs: FakeAutopsy())
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

