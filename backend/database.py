from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from Hindsight.config import get_settings

client: AsyncIOMotorClient | None = None
database: AsyncIOMotorDatabase | None = None


def _get_database() -> AsyncIOMotorDatabase:
    """Initialize MongoDB only when a MongoDB-backed endpoint is requested."""
    global client, database
    if database is None:
        settings = get_settings()
        if not settings.mongo_uri:
            raise RuntimeError("MONGO_URI must be set for MongoDB-backed endpoints.")
        client = AsyncIOMotorClient(settings.mongo_uri)
        database = client[settings.database_name]
    return database


async def get_database() -> AsyncIOMotorDatabase:
    """Return the shared async MongoDB database for route dependencies."""
    return _get_database()


def close_database_client() -> None:
    """Close the MongoDB client when it was initialized during this process."""
    global client, database
    if client is not None:
        client.close()
        client = None
        database = None
