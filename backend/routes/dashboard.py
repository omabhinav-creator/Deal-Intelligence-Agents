"""Authenticated dashboard aggregates from the shared MongoDB database."""

from typing import Annotated

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..auth import get_current_user
from ..database import get_database


router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)
DatabaseDependency = Annotated[AsyncIOMotorDatabase, Depends(get_database)]


@router.get("/metrics")
async def dashboard_metrics(db: DatabaseDependency) -> dict[str, int]:
    deals = db["deals"]
    interactions = db["interactions"]
    deal_count = await deals.count_documents({})
    closed = {"won", "lost", "stalled"}
    open_count = await deals.count_documents({"status": {"$nin": list(closed)}})
    at_risk_count = await deals.count_documents(
        {"risk_level": {"$in": ["high", "medium"]}, "status": {"$nin": list(closed)}}
    )
    interaction_count = await interactions.count_documents({})
    return {
        "deal_count": deal_count,
        "open_deal_count": open_count,
        "at_risk_count": at_risk_count,
        "closed_deal_count": deal_count - open_count,
        "interaction_count": interaction_count,
    }