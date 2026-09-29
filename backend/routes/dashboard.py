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
OPEN_DEAL_STATUSES = ("open", "active", "in-progress")
AT_RISK_LEVELS = ("high", "medium", "High", "Medium")


@router.get("/metrics")
async def dashboard_metrics(db: DatabaseDependency) -> dict[str, int]:
    deals = db["deals"]
    interactions = db["interactions"]
    deal_count = await deals.count_documents({})
    open_status_filter = {"status": {"$in": list(OPEN_DEAL_STATUSES)}}
    open_count = await deals.count_documents(open_status_filter)
    at_risk_count = await deals.count_documents(
        {
            **open_status_filter,
            "risk_level": {"$in": list(AT_RISK_LEVELS)},
        }
    )
    interaction_count = await interactions.count_documents({})
    return {
        "deal_count": deal_count,
        "open_deal_count": open_count,
        "at_risk_count": at_risk_count,
        "closed_deal_count": deal_count - open_count,
        "interaction_count": interaction_count,
    }
