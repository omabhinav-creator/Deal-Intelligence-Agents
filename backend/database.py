import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "dealmind")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI must be set in the environment or .env file")

client: AsyncIOMotorClient = AsyncIOMotorClient(MONGO_URI)
database: AsyncIOMotorDatabase = client[DATABASE_NAME]


async def get_database() -> AsyncIOMotorDatabase:
    """Return the shared async MongoDB database for route dependencies."""
    return database