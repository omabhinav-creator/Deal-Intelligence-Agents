from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..database import get_database
from ..schemas import InteractionCreate, InteractionResponse

router = APIRouter(
    prefix="/api/deals/{deal_id}/interactions",
    tags=["interactions"],
)
DatabaseDependency = Annotated[AsyncIOMotorDatabase, Depends(get_database)]


async def _require_deal(deal_id: str, db: AsyncIOMotorDatabase) -> ObjectId:
    if not ObjectId.is_valid(deal_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid deal ID")

    object_id = ObjectId(deal_id)
    deal = await db["deals"].find_one({"_id": object_id}, {"_id": 1})
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return object_id


@router.post("", response_model=InteractionResponse, status_code=status.HTTP_201_CREATED)
async def create_interaction(
    deal_id: str,
    payload: InteractionCreate,
    db: DatabaseDependency,
) -> InteractionResponse:
    await _require_deal(deal_id, db)
    interaction_data = payload.model_dump(exclude={"deal_id"})
    interaction_data["deal_id"] = deal_id

    result = await db["interactions"].insert_one(interaction_data)
    created_interaction = await db["interactions"].find_one({"_id": result.inserted_id})
    if created_interaction is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Interaction was inserted but could not be retrieved",
        )
    return InteractionResponse.model_validate(created_interaction)


@router.get("", response_model=list[InteractionResponse])
async def list_interactions(
    deal_id: str,
    db: DatabaseDependency,
) -> list[InteractionResponse]:
    await _require_deal(deal_id, db)
    cursor = db["interactions"].find({"deal_id": deal_id}).sort(
        [("meeting_date", 1), ("_id", 1)]
    )
    documents = await cursor.to_list(length=None)
    return [InteractionResponse.model_validate(document) for document in documents]