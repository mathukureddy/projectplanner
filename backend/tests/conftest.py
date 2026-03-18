import os

import pytest
from pymongo import MongoClient


# Ensure tests never touch the real app DB.
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB", "project_planning_test")

# Keep failures fast if Mongo isn't running.
os.environ.setdefault("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "1000")
os.environ.setdefault("MONGODB_CONNECT_TIMEOUT_MS", "1000")


@pytest.fixture(autouse=True)
def _mongo_cleanup():
    """
    Drop test collections before and after each test so test projects don't persist.
    """
    mongo_uri = os.environ["MONGODB_URI"]
    db_name = os.environ["MONGODB_DB"]

    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=int(os.environ["MONGODB_SERVER_SELECTION_TIMEOUT_MS"]),
        connectTimeoutMS=int(os.environ["MONGODB_CONNECT_TIMEOUT_MS"]),
    )
    db = client[db_name]
    projects = db["projects"]
    tasks = db["tasks"]

    projects.delete_many({})
    tasks.delete_many({})

    yield

    projects.delete_many({})
    tasks.delete_many({})
    client.close()


@pytest.fixture(autouse=True)
def _reset_motor_client():
    """
    `backend/db.py` caches the Motor client globally. In async test runs,
    that can bind to an event loop that gets closed between tests.
    Resetting ensures each test uses a fresh client tied to its loop.
    """
    import db as db_module

    db_module._client = None

