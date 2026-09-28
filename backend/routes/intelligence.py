from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..database import get_database

router = APIRouter(prefix="/api/deals/{deal_id}", tags=["intelligence"])
DatabaseDependency = Annotated[AsyncIOMotorDatabase, Depends(get_database)]


async def _get_deal_or_404(deal_id: str, db: AsyncIOMotorDatabase) -> dict[str, Any]:
    if not ObjectId.is_valid(deal_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid deal ID")

    deal = await db["deals"].find_one({"_id": ObjectId(deal_id)})
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.get("/what-changed")
async def what_changed(deal_id: str, db: DatabaseDependency) -> dict[str, Any]:
    deal = await _get_deal_or_404(deal_id, db)
    return {
        "deal_id": deal_id,
        "changes": [
            {
                "field": "stage",
                "previous_value": "Discovery",
                "current_value": deal.get("stage", "Unknown"),
                "changed_at": None,
                "summary": "Mock analysis: stage history is not connected yet.",
            },
            {
                "field": "risk_level",
                "previous_value": None,
                "current_value": deal.get("risk_level", "Unknown"),
                "changed_at": None,
                "summary": "Current risk level recorded for this deal.",
            },
        ],
        "source": "mock",
    }


@router.get("/similar")
async def similar_deals(deal_id: str, db: DatabaseDependency) -> dict[str, Any]:
    deal = await _get_deal_or_404(deal_id, db)
    current_value = float(deal.get("value", 0))
    return {
        "deal_id": deal_id,
        "similar_deals": [
            {
                "id": "mock-deal-001",
                "company_name": "Northstar Systems",
                "value": round(current_value * 0.92, 2),
                "stage": "Negotiation",
                "status": "active",
                "similarity": 0.87,
                "match_reason": "Similar deal size and sales stage",
            },
            {
                "id": "mock-deal-002",
                "company_name": "Vertex Cloud",
                "value": round(current_value * 1.08, 2),
                "stage": "Proposal",
                "status": "won",
                "similarity": 0.74,
                "match_reason": "Similar deal value and customer profile",
            },
        ],
        "source": "mock",
    }