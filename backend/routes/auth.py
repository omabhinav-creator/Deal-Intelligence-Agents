"""MongoDB-backed authentication and profile endpoints."""

from datetime import datetime, timezone
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from ..auth import (
    create_session,
    ensure_auth_indexes,
    get_bearer_token,
    get_current_user,
    hash_password,
    hash_session_token,
    normalize_email,
    verify_password,
)
from ..database import get_database
from ..schemas import (
    AuthLoginRequest,
    AuthSessionResponse,
    AuthSignupRequest,
    ProfileUpdateRequest,
    UserPublic,
)


router = APIRouter(prefix="/api/auth", tags=["authentication"])
DatabaseDependency = Annotated[AsyncIOMotorDatabase, Depends(get_database)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _safe_user(document: dict[str, Any]) -> UserPublic:
    return UserPublic.model_validate(document)


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )


@router.post("/signup", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: AuthSignupRequest, db: DatabaseDependency) -> AuthSessionResponse:
    """Create a user, persist only a password hash, and start a session."""
    await ensure_auth_indexes(db)
    email = normalize_email(payload.email)
    user = {
        "name": payload.name.strip(),
        "email": email,
        "password_hash": hash_password(payload.password),
        "role": "member",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    try:
        result = await db["users"].insert_one(user)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        ) from exc
    user["_id"] = result.inserted_id
    token = await create_session(db, result.inserted_id)
    return AuthSessionResponse(access_token=token, user=_safe_user(user))


@router.post("/login", response_model=AuthSessionResponse)
async def login(payload: AuthLoginRequest, db: DatabaseDependency) -> AuthSessionResponse:
    """Verify stored scrypt credentials and issue a server-validated session."""
    email = normalize_email(payload.email)
    user = await db["users"].find_one({"email": email})
    if user is None or not verify_password(payload.password, user.get("password_hash", "")):
        raise _invalid_credentials()
    token = await create_session(db, user["_id"])
    return AuthSessionResponse(access_token=token, user=_safe_user(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    db: DatabaseDependency,
    _: CurrentUser,
    token: Annotated[str, Depends(get_bearer_token)],
) -> None:
    """Invalidate the active opaque bearer session."""
    await db["sessions"].delete_one({"token_hash": hash_session_token(token)})


@router.get("/me", response_model=UserPublic)
async def current_user(_: CurrentUser) -> UserPublic:
    return _safe_user(_)


@router.put("/profile", response_model=UserPublic)
async def update_profile(
    payload: ProfileUpdateRequest,
    db: DatabaseDependency,
    user: CurrentUser,
) -> UserPublic:
    """Update only the authenticated user's mutable public profile fields."""
    updates: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.email is not None:
        email = normalize_email(payload.email)
        if email != user["email"]:
            existing = await db["users"].find_one({"email": email}, {"_id": 1})
            if existing is not None and existing["_id"] != user["_id"]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with that email already exists.",
                )
            updates["email"] = email
    if len(updates) == 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide a name or email to update.")
    try:
        await db["users"].update_one({"_id": user["_id"]}, {"$set": updates})
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        ) from exc
    updated = await db["users"].find_one({"_id": user["_id"]})
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _safe_user(updated)
