import os
from datetime import date, datetime
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


def normalize_dates(value: Any) -> Any:
    """
    Convert `datetime.date` into `datetime` so Mongo (bson encoder) can persist it.
    Mongo can encode `datetime` but not plain `datetime.date`.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        # Store at midnight (local/naive) to keep dates stable.
        return datetime(value.year, value.month, value.day)
    return value


def normalize_document(doc: dict) -> dict:
    """Recursively normalize date objects inside a document dict."""
    normalized: dict[str, Any] = {}
    for k, v in doc.items():
        if isinstance(v, dict):
            normalized[k] = normalize_document(v)
        elif isinstance(v, list):
            normalized[k] = [normalize_dates(i) for i in v]
        else:
            normalized[k] = normalize_dates(v)
    return normalized


def apply_status_completion_rules(doc: dict) -> dict:
    """
    Smartsheet-like rule:
    - `Not Started` => percent_complete = 0
    - `Complete` => percent_complete = 100
    """
    status = doc.get("status")
    if status == "Not Started":
        doc["percent_complete"] = 0
    elif status == "Complete":
        doc["percent_complete"] = 100
    return doc

