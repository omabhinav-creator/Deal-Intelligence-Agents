from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..database import get_database
from ..auth import get_current_user
from ..schemas import DealCreate, DealResponse

router = APIRouter(
    prefix="/api/deals", tags=["deals"], dependencies=[Depends(get_current_user)]
)
DatabaseDependency = Annotated[AsyncIOMotorDatabase, Depends(get_database)]


@router.get("", response_model=list[DealResponse])
async def list_deals(db: DatabaseDependency) -> list[DealResponse]:
    cursor = db["deals"].find({}).sort("_id", -1)
    documents = await cursor.to_list(length=None)
    return [DealResponse.model_validate(document) for document in documents]


@router.post("", response_model=DealResponse, status_code=status.HTTP_201_CREATED)
async def create_deal(payload: DealCreate, db: DatabaseDependency) -> DealResponse:
    deal_data = payload.model_dump()
    result = await db["deals"].insert_one(deal_data)
    created_deal = await db["deals"].find_one({"_id": result.inserted_id})
    if created_deal is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Deal was inserted but could not be retrieved",
        )
    return DealResponse.model_validate(created_deal)


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(deal_id: str, db: DatabaseDependency) -> DealResponse:
    if not ObjectId.is_valid(deal_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid deal ID")

    deal = await db["deals"].find_one({"_id": ObjectId(deal_id)})
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return DealResponse.model_validate(deal)
