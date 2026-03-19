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


@pytest.mark.asyncio
async def test_task_hierarchy_rollups_and_parent_validation():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        project_payload = {
            "name": "UT_Hierarchy_" + __import__("uuid").uuid4().hex[:8],
            "status": "On Track",
            "tasks": [{"name": "Parent Task"}],
        }
        project_resp = await ac.post("/projects/", json=project_payload)
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        all_tasks = await ac.get("/tasks/", params={"project_id": project_id})
        assert all_tasks.status_code == 200
        parent_id = all_tasks.json()[0]["id"]

        child1 = await ac.post(
            "/tasks/",
            json={
                "project_id": project_id,
                "name": "Child 1",
                "status": "Complete",
                "percent_complete": 100,
                "parent_task_id": parent_id,
            },
        )
        assert child1.status_code == 201

        child2 = await ac.post(
            "/tasks/",
            json={
                "project_id": project_id,
                "name": "Child 2",
                "status": "Not Started",
                "percent_complete": 0,
                "parent_task_id": parent_id,
            },
        )
        assert child2.status_code == 201

        # Parent rollup should aggregate children (100 + 0)/2 => 50.
        refreshed = await ac.get("/tasks/", params={"project_id": project_id})
        assert refreshed.status_code == 200
        parent = next(t for t in refreshed.json() if t["id"] == parent_id)
        assert parent["child_count"] == 2
        assert parent["rollup_percent_complete"] == 50
        assert parent["rollup_status"] == "In Progress"

        # Invalid parent reference should be rejected.
        invalid_parent = await ac.post(
            "/tasks/",
            json={
                "project_id": project_id,
                "name": "Bad Child",
                "parent_task_id": "000000000000000000000000",
            },
        )
        assert invalid_parent.status_code == 400


@pytest.mark.asyncio
async def test_dependencies_critical_path_and_baseline_variance():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        project_payload = {
            "name": "UT_Critical_" + __import__("uuid").uuid4().hex[:8],
            "status": "On Track",
            "end_date": "2026-03-20",
            "baseline_end": "2026-03-18",
            "tasks": [{"name": "T1", "duration_days": 2, "baseline_start": "2026-03-01", "baseline_end": "2026-03-02"}],
        }
        project_resp = await ac.post("/projects/", json=project_payload)
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]
        assert project_resp.json()["schedule_status"] == "Late"
        assert project_resp.json()["baseline_variance_days"] == 2

        tasks_resp = await ac.get("/tasks/", params={"project_id": project_id})
        t1 = tasks_resp.json()[0]

        t2_resp = await ac.post(
            "/tasks/",
            json={
                "project_id": project_id,
                "name": "T2",
                "duration_days": 3,
                "predecessors": [t1["id"]],
            },
        )
        assert t2_resp.status_code == 201
        t2_id = t2_resp.json()["id"]

        refreshed = await ac.get("/tasks/", params={"project_id": project_id})
        assert refreshed.status_code == 200
        by_name = {t["name"]: t for t in refreshed.json()}
        assert by_name["T1"]["is_critical"] is True
        assert by_name["T2"]["is_critical"] is True
        assert by_name["T2"]["earliest_start_day"] == by_name["T1"]["earliest_finish_day"]

        # Try to create cycle: T1 depends on T2 should fail.
        cycle_resp = await ac.patch(
            f"/tasks/{t1['id']}",
            json={"predecessors": [t2_id]},
        )
        assert cycle_resp.status_code == 400


@pytest.mark.asyncio
async def test_snapshot_project_baseline_endpoint():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        project_payload = {
            "name": "UT_BaselineSnap_" + __import__("uuid").uuid4().hex[:8],
            "status": "On Track",
            "start_date": "2026-03-10",
            "end_date": "2026-03-20",
            "tasks": [
                {
                    "name": "Task Snap",
                    "start_date": "2026-03-11",
                    "end_date": "2026-03-12",
                }
            ],
        }
        project_resp = await ac.post("/projects/", json=project_payload)
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        snap = await ac.post(f"/projects/{project_id}/baseline/snapshot")
        assert snap.status_code == 200
        assert snap.json()["status"] == "ok"
        assert snap.json()["updated_tasks"] == 1

        project_after = await ac.get(f"/projects/{project_id}")
        assert project_after.status_code == 200
        assert project_after.json()["baseline_start"] is not None
        assert project_after.json()["baseline_end"] is not None

        tasks_after = await ac.get("/tasks/", params={"project_id": project_id})
        assert tasks_after.status_code == 200
        assert tasks_after.json()[0]["baseline_start"] is not None
        assert tasks_after.json()[0]["baseline_end"] is not None

