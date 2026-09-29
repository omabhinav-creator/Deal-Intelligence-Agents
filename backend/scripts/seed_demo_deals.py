"""Idempotently seed the four existing DealMind demo deal records into MongoDB."""

import asyncio

DEMO_DEALS = (
    {
        "company_name": "TechNova",
        "value": 120000,
        "stage": "Negotiation",
        "risk_level": "Medium",
        "status": "active",
    },
    {
        "company_name": "Acme Corp",
        "value": 85000,
        "stage": "Proposal",
        "risk_level": "Low",
        "status": "active",
    },
    {
        "company_name": "Nova Systems",
        "value": 210000,
        "stage": "Negotiation",
        "risk_level": "High",
        "status": "active",
    },
    {
        "company_name": "Quantum Systems",
        "value": 180000,
        "stage": "Negotiation",
        "risk_level": "High",
        "status": "active",
    },
)


async def seed_demo_deals(db=None) -> dict[str, str]:
    """Insert missing demo deals without overwriting existing company records."""
    if db is None:
        from backend.database import database

        db = database
    deals = db["deals"]
    await deals.create_index(
        "company_name",
        unique=True,
        name="unique_deal_company_name",
    )

    results: dict[str, str] = {}
    for deal in DEMO_DEALS:
        result = await deals.update_one(
            {"company_name": deal["company_name"]},
            {"$setOnInsert": deal},
            upsert=True,
        )
        results[deal["company_name"]] = (
            "created" if result.upserted_id is not None else "already exists"
        )
    return results


async def main() -> None:
    from backend.database import client, database

    try:
        results = await seed_demo_deals()
        for company_name, result in results.items():
            print(f"{company_name}: {result}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
