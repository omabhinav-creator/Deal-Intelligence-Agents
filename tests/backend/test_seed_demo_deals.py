import asyncio
from types import SimpleNamespace

from backend.scripts.seed_demo_deals import DEMO_DEALS, seed_demo_deals


class FakeDealsCollection:
    def __init__(self):
        self.documents = {}
        self.index = None

    async def create_index(self, field, *, unique, name):
        self.index = (field, unique, name)

    async def update_one(self, query, update, *, upsert):
        company_name = query["company_name"]
        if company_name in self.documents:
            return SimpleNamespace(upserted_id=None)
        assert upsert is True
        self.documents[company_name] = update["$setOnInsert"].copy()
        return SimpleNamespace(upserted_id=f"generated-{company_name}")


class FakeDatabase:
    def __init__(self):
        self.deals = FakeDealsCollection()

    def __getitem__(self, collection):
        assert collection == "deals"
        return self.deals


def test_seed_is_idempotent_and_uses_only_existing_demo_deals():
    db = FakeDatabase()

    first_run = asyncio.run(seed_demo_deals(db))
    second_run = asyncio.run(seed_demo_deals(db))

    names = [deal["company_name"] for deal in DEMO_DEALS]
    assert list(db.deals.documents) == names
    assert first_run == {name: "created" for name in names}
    assert second_run == {name: "already exists" for name in names}
    assert db.deals.index == (
        "company_name",
        True,
        "unique_deal_company_name",
    )
