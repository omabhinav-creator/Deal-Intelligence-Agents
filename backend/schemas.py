from datetime import datetime
from typing import Annotated, Any

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, WithJsonSchema, field_validator


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


class AuthSignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)

    @field_validator("name", "email", mode="before")
    @classmethod
    def strip_identity_fields(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class AuthLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class UserPublic(MongoModel):
    id: PyObjectId = Field(validation_alias="_id", serialization_alias="id")
    name: str
    email: str
    role: str
    created_at: datetime


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, min_length=3, max_length=320)


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
