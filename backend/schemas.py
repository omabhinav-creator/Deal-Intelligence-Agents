from datetime import datetime
from typing import Annotated, Any

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, WithJsonSchema


def _validate_object_id(value: Any) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, str):
        return value
    raise ValueError("id must be a string or MongoDB ObjectId")


PyObjectId = Annotated[
    str,
    BeforeValidator(_validate_object_id),
    WithJsonSchema({"type": "string"}),
]


class MongoModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class DealBase(MongoModel):
    company_name: str
    value: float
    stage: str
    risk_level: str
    status: str


class DealCreate(DealBase):
    pass


class DealResponse(DealBase):
    id: PyObjectId = Field(validation_alias="_id", serialization_alias="id")


class InteractionBase(MongoModel):
    deal_id: str
    meeting_date: datetime
    content: str
    key_takeaway: str


class InteractionCreate(InteractionBase):
    pass


class InteractionResponse(InteractionBase):
    id: PyObjectId = Field(validation_alias="_id", serialization_alias="id")


class StakeholderBase(MongoModel):
    deal_id: str
    name: str
    role: str
    concern: str


class StakeholderCreate(StakeholderBase):
    pass


class StakeholderResponse(StakeholderBase):
    id: PyObjectId = Field(validation_alias="_id", serialization_alias="id")