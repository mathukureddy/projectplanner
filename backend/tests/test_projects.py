import pytest
from httpx import AsyncClient

from main import create_app


@pytest.mark.asyncio
async def test_health_endpoint():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_project_with_tasks_and_duplicate_name():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        payload = {
            "name": "UT_Project_" + __import__("uuid").uuid4().hex[:8],
            "status": "On Track",
            "tasks": [{"name": "Task A", "start_date": "2026-03-18", "end_date": "2026-03-25"}],
        }

        r1 = await ac.post("/projects/", json=payload)
        assert r1.status_code == 201

        # Duplicate name should be rejected.
        r2 = await ac.post("/projects/", json=payload)
        assert r2.status_code == 409
        assert r2.json()["detail"] == "Project name already exists"


@pytest.mark.asyncio
async def test_collections_empty_after_previous_test():
    """
    The autouse cleanup in `conftest.py` should guarantee no test projects persist.
    """
    # Using the API to confirm emptiness (avoid direct DB coupling in test).
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/projects/")
        assert resp.status_code == 200
        assert resp.json() == []

