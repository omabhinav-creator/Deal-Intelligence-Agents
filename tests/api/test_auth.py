from copy import deepcopy
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from backend.auth import verify_password
from backend.database import get_database
from backend.main import app


class FakeCollection:
    def __init__(self):
        self.documents = []

    async def create_index(self, *_args, **_kwargs):
        return "created"

    async def count_documents(self, query):
        def matches(document):
            for key, expected in query.items():
                actual = document.get(key)
                if isinstance(expected, dict) and "$nin" in expected:
                    if actual in expected["$nin"]:
                        return False
                elif isinstance(expected, dict) and "$in" in expected:
                    if actual not in expected["$in"]:
                        return False
                elif actual != expected:
                    return False
            return True

        return sum(matches(document) for document in self.documents)

    async def insert_one(self, document):
        if "email" in document and any(
            item.get("email") == document["email"] for item in self.documents
        ):
            raise DuplicateKeyError("duplicate email")
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    async def find_one(self, query, _projection=None):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return deepcopy(document)
        return None

    async def update_one(self, query, update):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                document.update(deepcopy(update.get("$set", {})))
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    async def delete_one(self, query):
        for index, document in enumerate(self.documents):
            if all(document.get(key) == value for key, value in query.items()):
                self.documents.pop(index)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


class FakeDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())


@pytest.fixture
def auth_client():
    database = FakeDatabase()
    app.dependency_overrides[get_database] = lambda: database
    with TestClient(app) as test_client:
        yield test_client, database
    app.dependency_overrides.pop(get_database, None)


def signup(client):
    return client.post(
        "/api/auth/signup",
        json={
            "name": "  Ada Lovelace  ",
            "email": "  ADA@Example.com ",
            "password": "  correct horse  ",
        },
    )


def test_signup_normalizes_email_hashes_password_and_returns_safe_session(auth_client):
    client, database = auth_client
    response = signup(client)

    assert response.status_code == 201
    result = response.json()
    assert result["user"]["name"] == "Ada Lovelace"
    assert result["user"]["email"] == "ada@example.com"
    assert "password" not in result
    assert "password_hash" not in result["user"]

    stored_user = database["users"].documents[0]
    assert {"name", "email", "password_hash", "role", "created_at", "updated_at"} <= set(stored_user)
    assert stored_user["password_hash"] != "  correct horse  "
    assert verify_password("  correct horse  ", stored_user["password_hash"])
    assert not verify_password("correct horse", stored_user["password_hash"])


def test_duplicate_signup_returns_useful_conflict(auth_client):
    client, _database = auth_client
    assert signup(client).status_code == 201

    response = signup(client)

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_login_failures_current_user_and_successful_login(auth_client):
    client, _database = auth_client
    assert signup(client).status_code == 201

    wrong_password = client.post(
        "/api/auth/login",
        json={"email": "ada@example.com", "password": "wrong password"},
    )
    unknown_email = client.post(
        "/api/auth/login",
        json={"email": "unknown@example.com", "password": "wrong password"},
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]
    assert client.get("/api/auth/me").status_code == 401

    login_response = client.post(
        "/api/auth/login",
        json={"email": "ada@example.com", "password": "  correct horse  "},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    current = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert current.status_code == 200
    assert current.json()["email"] == "ada@example.com"
    assert "password_hash" not in current.json()


def test_profile_update_persists_and_logout_invalidates_session(auth_client):
    client, database = auth_client
    session = signup(client).json()
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    updated = client.put(
        "/api/auth/profile",
        headers=headers,
        json={"name": "Ada Byron", "email": " ADA@Example.org "},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Ada Byron"
    assert updated.json()["email"] == "ada@example.org"

    refreshed = client.get("/api/auth/me", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["name"] == "Ada Byron"
    assert refreshed.json()["email"] == "ada@example.org"
    stored_user = database["users"].documents[0]
    assert stored_user["name"] == "Ada Byron"
    assert stored_user["email"] == "ada@example.org"

    logged_out = client.post("/api/auth/logout", headers=headers)
    assert logged_out.status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_protected_api_rejects_unauthenticated_requests(auth_client):
    client, _database = auth_client

    response = client.get("/api/deals")

    assert response.status_code == 401


def test_dashboard_metrics_use_mongodb_counts(auth_client):
    client, database = auth_client
    session = signup(client).json()
    database["deals"].documents.extend(
        [
            {"status": "active", "risk_level": "high"},
            {"status": "won", "risk_level": "low"},
            {"status": "pending", "risk_level": "high"},
            {"status": "in-progress", "risk_level": "Medium"},
        ]
    )
    database["interactions"].documents.append({"deal_id": "deal-a"})

    response = client.get(
        "/api/dashboard/metrics",
        headers={"Authorization": f"Bearer {session['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "deal_count": 4,
        "open_deal_count": 2,
        "at_risk_count": 2,
        "closed_deal_count": 2,
        "interaction_count": 1,
    }
