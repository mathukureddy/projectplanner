import os
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv


load_dotenv()

_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        # Fail fast when Mongo isn't running to avoid long hangs in API calls.
        _client = AsyncIOMotorClient(
            mongo_uri,
            serverSelectionTimeoutMS=int(os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "2000")),
            connectTimeoutMS=int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "2000")),
        )
    return _client


def get_database() -> AsyncIOMotorDatabase:
    db_name = os.getenv("MONGODB_DB", "project_planning")
    return get_mongo_client()[db_name]


async def get_collection(name: str) -> Any:
    db = get_database()
    return db[name]

