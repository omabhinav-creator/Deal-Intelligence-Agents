"""Password and opaque-session authentication helpers for DealMind."""

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from bson import ObjectId
from fastapi import Depends, Header, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from Hindsight.config import get_settings

from .database import get_database


DatabaseDependency = Annotated[AsyncIOMotorDatabase, Depends(get_database)]
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


def normalize_email(email: str) -> str:
    """Return the canonical email value used for unique user lookup."""
    return email.strip().casefold()


def hash_password(password: str) -> str:
    """Use scrypt with a fresh random salt; plaintext is never persisted."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return "$".join(
        (
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    """Safely verify a password against the stored scrypt representation."""
    try:
        algorithm, n, r, p, encoded_salt, encoded_digest = encoded_hash.split("$")
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
        expected = base64.urlsafe_b64decode(encoded_digest.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p)
        )
    except (ValueError, TypeError, UnicodeError):
        return False
    return hmac.compare_digest(actual, expected)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def ensure_auth_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create the database constraints required for user and session safety."""
    await db["users"].create_index("email", unique=True, name="unique_user_email")
    await db["sessions"].create_index(
        "token_hash", unique=True, name="unique_session_token"
    )
    await db["sessions"].create_index("expires_at", expireAfterSeconds=0)


async def create_session(db: AsyncIOMotorDatabase, user_id: ObjectId) -> str:
    """Create an opaque bearer token; only its SHA-256 digest reaches MongoDB."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=get_settings().auth_session_ttl_hours
    )
    await db["sessions"].insert_one(
        {
            "user_id": user_id,
            "token_hash": hash_session_token(token),
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
        }
    )
    return token


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    db: DatabaseDependency,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Validate a bearer session and return its user without password fields."""
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized()
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise _unauthorized()
    session = await db["sessions"].find_one({"token_hash": hash_session_token(token)})
    now = datetime.now(timezone.utc)
    if session is None or session.get("expires_at") is None:
        raise _unauthorized()
    expires_at = session["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        await db["sessions"].delete_one({"_id": session["_id"]})
        raise _unauthorized()
    user = await db["users"].find_one({"_id": session.get("user_id")})
    if user is None:
        raise _unauthorized()
    return user


async def get_bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Return a syntactically valid bearer token for logout invalidation."""
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized()
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise _unauthorized()
    return token
