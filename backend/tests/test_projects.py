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
        body = snap.json()
        assert body["status"] == "ok"
        assert body["updated_tasks"] == 1
        assert body["project"]["id"] == project_id

        project_after = await ac.get(f"/projects/{project_id}")
        assert project_after.status_code == 200
        assert project_after.json()["baseline_start"] is not None
        assert project_after.json()["baseline_end"] is not None

        tasks_after = await ac.get("/tasks/", params={"project_id": project_id})
        assert tasks_after.status_code == 200
        assert tasks_after.json()[0]["baseline_start"] is not None
        assert tasks_after.json()[0]["baseline_end"] is not None


@pytest.mark.asyncio
async def test_baseline_snapshot_rolls_up_task_dates_when_project_dates_empty():
    """Project plan dates often live only on tasks; snapshot should still set project baseline."""
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        project_resp = await ac.post(
            "/projects/",
            json={
                "name": "UT_BaselineRollup_" + __import__("uuid").uuid4().hex[:8],
                "status": "On Track",
                "tasks": [
                    {
                        "name": "A",
                        "start_date": "2026-04-01",
                        "end_date": "2026-04-05",
                    },
                    {
                        "name": "B",
                        "start_date": "2026-04-10",
                        "end_date": "2026-04-20",
                    },
                ],
            },
        )
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]
        assert project_resp.json().get("start_date") in (None, "")

        snap = await ac.post(f"/projects/{project_id}/baseline/snapshot")
        assert snap.status_code == 200
        proj = snap.json()["project"]
        assert proj["baseline_start"] is not None
        assert proj["baseline_end"] is not None


@pytest.mark.asyncio
async def test_collaboration_comments_shares_and_alerts():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        project_resp = await ac.post(
            "/projects/",
            json={
                "name": "UT_Collab_" + __import__("uuid").uuid4().hex[:8],
                "status": "On Track",
                "tasks": [{"name": "Only Task"}],
            },
        )
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]
        task_id = (await ac.get("/tasks/", params={"project_id": project_id})).json()[0]["id"]

        share = await ac.patch(
            f"/projects/{project_id}",
            json={"shares": [{"email": "a@example.com", "role": "editor"}]},
        )
        assert share.status_code == 200
        assert share.json()["shares"][0]["email"] == "a@example.com"

        c = await ac.post(
            "/comments/?project_id=" + project_id,
            json={"task_id": task_id, "author": "Alice", "body": "Hello"},
        )
        assert c.status_code == 201
        lst = await ac.get("/comments/", params={"task_id": task_id, "project_id": project_id})
        assert lst.status_code == 200
        assert len(lst.json()) == 1

        alert = await ac.post(
            "/alerts/",
            json={
                "project_id": project_id,
                "title": "Note",
                "message": "Something happened",
                "task_id": task_id,
            },
        )
        assert alert.status_code == 201
        alerts = await ac.get("/alerts/", params={"project_id": project_id})
        assert alerts.status_code == 200
        assert len(alerts.json()) >= 1


@pytest.mark.asyncio
async def test_automation_notify_on_completion_creates_alert_on_status_change():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        project_resp = await ac.post(
            "/projects/",
            json={
                "name": "UT_AutoComplete_" + __import__("uuid").uuid4().hex[:8],
                "status": "On Track",
                "tasks": [{"name": "Task Auto"}],
            },
        )
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        task_id = (await ac.get("/tasks/", params={"project_id": project_id})).json()[0]["id"]

        # Mark task as Complete; backend should create `task_completed` alert.
        upd = await ac.patch(
            f"/tasks/{task_id}",
            json={"status": "Complete"},
        )
        assert upd.status_code == 200

        alerts = await ac.get("/alerts/", params={"project_id": project_id})
        assert alerts.status_code == 200
        assert any(a.get("kind") == "task_completed" for a in alerts.json())


@pytest.mark.asyncio
async def test_automation_time_trigger_overdue_alerts_on_run():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        project_resp = await ac.post(
            "/projects/",
            json={
                "name": "UT_AutoOverdue_" + __import__("uuid").uuid4().hex[:8],
                "status": "On Track",
                "tasks": [
                    {
                        "name": "Old Task",
                        "end_date": "2020-01-01",
                        "start_date": "2020-01-01",
                        "status": "In Progress",
                        "percent_complete": 10,
                    }
                ],
            },
        )
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        run = await ac.post(f"/projects/{project_id}/automations/run")
        assert run.status_code == 200

        alerts = await ac.get("/alerts/", params={"project_id": project_id})
        assert alerts.status_code == 200
        assert any(a.get("kind") == "task_overdue" for a in alerts.json())


@pytest.mark.asyncio
async def test_reporting_portfolio_and_project_rollups():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        project_resp = await ac.post(
            "/projects/",
            json={
                "name": "UT_Report_" + __import__("uuid").uuid4().hex[:8],
                "status": "On Track",
                "tasks": [
                    {"name": "Done", "status": "Complete", "percent_complete": 100},
                    {"name": "Late", "status": "In Progress", "end_date": "2020-01-01", "percent_complete": 50},
                ],
            },
        )
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        portfolio = await ac.get("/reports/portfolio")
        assert portfolio.status_code == 200
        body = portfolio.json()
        assert body["totals"]["project_count"] >= 1
        assert body["totals"]["task_count"] >= 2
        assert "projects" in body

        project_report = await ac.get(f"/reports/projects/{project_id}")
        assert project_report.status_code == 200
        pbody = project_report.json()
        assert pbody["project"]["id"] == project_id
        assert pbody["totals"]["task_count"] == 2
        assert pbody["totals"]["completed_task_count"] == 1


@pytest.mark.asyncio
async def test_data_features_formulas_governance_and_cell_history():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        p = await ac.post(
            "/projects/",
            json={
                "name": "UT_DataFeat_" + __import__("uuid").uuid4().hex[:8],
                "status": "On Track",
                "tasks": [{"name": "T1", "percent_complete": 40}],
            },
        )
        assert p.status_code == 201
        project_id = p.json()["id"]
        task_id = (await ac.get("/tasks/", params={"project_id": project_id})).json()[0]["id"]

        # Governance: lock status field.
        gov = await ac.patch(
            f"/projects/{project_id}/governance",
            json={"locked_fields": ["status"], "restrict_locked_to_admin": True},
        )
        assert gov.status_code == 200

        blocked = await ac.patch(
            f"/tasks/{task_id}",
            json={"status": "Complete"},
            headers={"x-user-role": "editor", "x-user-name": "alice"},
        )
        assert blocked.status_code == 403

        allowed = await ac.patch(
            f"/tasks/{task_id}",
            json={"status": "Complete"},
            headers={"x-user-role": "admin", "x-user-name": "admin"},
        )
        assert allowed.status_code == 200

        # Formula writes into a target field and creates cell history.
        formulas = await ac.patch(
            f"/projects/{project_id}/formulas",
            json=[
                {
                    "name": "Half progress",
                    "target_field": "duration_days",
                    "expression": "percent_complete/2",
                    "enabled": True,
                }
            ],
        )
        assert formulas.status_code == 200

        eval_res = await ac.post(f"/projects/{project_id}/formulas/evaluate")
        assert eval_res.status_code == 200
        assert eval_res.json()["applied"] >= 1

        history = await ac.get(f"/projects/{project_id}/cell-history", params={"task_id": task_id})
        assert history.status_code == 200
        assert len(history.json()) >= 1


@pytest.mark.asyncio
async def test_integrations_config_test_and_events():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        p = await ac.post(
            "/projects/",
            json={"name": "UT_Integrations_" + __import__("uuid").uuid4().hex[:8], "tasks": [{"name": "T1"}]},
        )
        assert p.status_code == 201
        project_id = p.json()["id"]

        patch = await ac.patch(
            f"/projects/{project_id}/integrations",
            json={
                "integrations": [
                    {"type": "webhook", "enabled": True, "endpoint": "https://example.com/hook"},
                    {"type": "email", "enabled": False},
                ]
            },
        )
        assert patch.status_code == 200
        assert len(patch.json()) == 2

        send = await ac.post(
            f"/projects/{project_id}/integrations/test",
            json={"integration_type": "webhook", "event_type": "task_completed", "payload": {"task_id": "abc"}},
        )
        assert send.status_code == 200

        inbound = await ac.post(
            f"/projects/{project_id}/integrations/webhook/webhook",
            json={"source": "external-system", "status": "ok"},
        )
        assert inbound.status_code == 200

        events = await ac.get(f"/projects/{project_id}/integrations/events")
        assert events.status_code == 200
        assert len(events.json()) >= 2


@pytest.mark.asyncio
async def test_integrations_auto_events_for_task_completion_and_overdue():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        p = await ac.post(
            "/projects/",
            json={
                "name": "UT_IntAuto_" + __import__("uuid").uuid4().hex[:8],
                "tasks": [
                    {"name": "Old Task", "status": "In Progress", "start_date": "2020-01-01", "end_date": "2020-01-01"},
                    {"name": "Soon Done", "status": "Not Started"},
                ],
            },
        )
        assert p.status_code == 201
        project_id = p.json()["id"]

        cfg = await ac.patch(
            f"/projects/{project_id}/integrations",
            json={"integrations": [{"type": "webhook", "enabled": True, "endpoint": "https://example.com/hook"}]},
        )
        assert cfg.status_code == 200

        tasks = await ac.get("/tasks/", params={"project_id": project_id})
        assert tasks.status_code == 200
        by_name = {t["name"]: t for t in tasks.json()}
        done_task_id = by_name["Soon Done"]["id"]

        complete = await ac.patch(f"/tasks/{done_task_id}", json={"status": "Complete"})
        assert complete.status_code == 200

        overdue = await ac.post(f"/projects/{project_id}/automations/run")
        assert overdue.status_code == 200

        events = await ac.get(f"/projects/{project_id}/integrations/events")
        assert events.status_code == 200
        event_types = [e["event_type"] for e in events.json()]
        assert "task_completed" in event_types
        assert "overdue_alert_created" in event_types


@pytest.mark.asyncio
async def test_auth_register_login_and_me():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        reg = await ac.post(
            "/auth/register",
            json={
                "username": "user_a",
                "email": "user_a@example.com",
                "password": "secret123",
                "role": "editor",
            },
        )
        assert reg.status_code == 201

        login = await ac.post("/auth/login", json={"username": "user_a", "password": "secret123"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        assert token

        me = await ac.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["username"] == "user_a"


@pytest.mark.asyncio
async def test_intake_form_public_submit_creates_task():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        p = await ac.post(
            "/projects/",
            json={
                "name": "UT_Intake_" + __import__("uuid").uuid4().hex[:8],
                "tasks": [{"name": "Seed"}],
            },
        )
        assert p.status_code == 201
        pid = p.json()["id"]

        form_body = {
            "name": "Bug report",
            "enabled": True,
            "fields": [
                {"key": "title", "label": "Title", "type": "text", "required": True},
                {"key": "details", "label": "Details", "type": "textarea", "required": False},
            ],
            "task_name_field": "title",
            "task_description_field": "details",
            "default_status": "Not Started",
        }
        fr = await ac.post(f"/projects/{pid}/intake-forms", json=form_body)
        assert fr.status_code == 201
        slug = fr.json()["slug"]
        fid = fr.json()["id"]

        pub = await ac.get(f"/intake/public/{slug}")
        assert pub.status_code == 200
        assert pub.json()["name"] == "Bug report"

        sub = await ac.post(
            f"/intake/public/{slug}/submit",
            json={"responses": {"title": "Login broken", "details": "Cannot submit"}},
        )
        assert sub.status_code == 200
        assert sub.json()["task_id"]

        tasks = await ac.get("/tasks/", params={"project_id": pid})
        assert any(t["name"] == "Login broken" for t in tasks.json())

        subs = await ac.get(f"/projects/{pid}/intake-forms/{fid}/submissions")
        assert subs.status_code == 200
        assert len(subs.json()) >= 1

        off = await ac.patch(f"/projects/{pid}/intake-forms/{fid}", json={"enabled": False})
        assert off.status_code == 200
        gone = await ac.get(f"/intake/public/{slug}")
        assert gone.status_code == 404


@pytest.mark.asyncio
async def test_auth_bootstrap_admin_case_insensitive():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        login = await ac.post("/auth/login", json={"username": "Admin", "password": "admin123"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        me = await ac.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_admin_user_management_requires_admin():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        reg = await ac.post(
            "/auth/register",
            json={
                "username": "editor_only",
                "email": "ed@example.com",
                "password": "secret123",
                "role": "editor",
            },
        )
        assert reg.status_code == 201
        tok = (await ac.post("/auth/login", json={"username": "editor_only", "password": "secret123"})).json()[
            "access_token"
        ]
        blocked = await ac.get("/auth/admin/users", headers={"Authorization": f"Bearer {tok}"})
        assert blocked.status_code == 403


@pytest.mark.asyncio
async def test_admin_user_management_crud():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        admin_tok = (await ac.post("/auth/login", json={"username": "admin", "password": "admin123"})).json()[
            "access_token"
        ]
        headers = {"Authorization": f"Bearer {admin_tok}"}

        empty = await ac.get("/auth/admin/users", headers=headers)
        assert empty.status_code == 200
        assert empty.json() == []

        created = await ac.post(
            "/auth/admin/users",
            headers=headers,
            json={
                "username": "managed",
                "email": "managed@example.com",
                "password": "pw123456",
                "role": "viewer",
            },
        )
        assert created.status_code == 201
        uid = created.json()["id"]

        listed = await ac.get("/auth/admin/users", headers=headers)
        assert len(listed.json()) == 1

        patched = await ac.patch(
            f"/auth/admin/users/{uid}",
            headers=headers,
            json={"role": "editor"},
        )
        assert patched.status_code == 200
        assert patched.json()["role"] == "editor"

        await ac.post(
            "/auth/admin/users",
            headers=headers,
            json={
                "username": "second_admin",
                "email": "sa@example.com",
                "password": "pw123456",
                "role": "admin",
            },
        )

        del_first = await ac.delete(f"/auth/admin/users/{uid}", headers=headers)
        assert del_first.status_code == 204

        listed2 = await ac.get("/auth/admin/users", headers=headers)
        assert len(listed2.json()) == 1


@pytest.mark.asyncio
async def test_resource_workload_report():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        p = await ac.post(
            "/projects/",
            json={
                "name": "UT_Workload_" + __import__("uuid").uuid4().hex[:8],
                "status": "On Track",
                "tasks": [
                    {
                        "name": "A1",
                        "assigned_to": "alice",
                        "status": "In Progress",
                        "start_date": "2026-03-01",
                        "end_date": "2026-03-10",
                    },
                    {
                        "name": "A2",
                        "assigned_to": "alice",
                        "status": "Not Started",
                        "duration_days": 8,
                    },
                    {
                        "name": "B1",
                        "assigned_to": "bob",
                        "status": "In Progress",
                        "start_date": "2026-03-05",
                        "end_date": "2026-03-06",
                    },
                    {
                        "name": "C_done",
                        "assigned_to": "charlie",
                        "status": "Complete",
                        "duration_days": 10,
                    },
                ],
            },
        )
        assert p.status_code == 201
        project_id = p.json()["id"]

        rep = await ac.get(
            "/reports/workload",
            params={"project_id": project_id, "window_days": 7, "capacity_hours_per_day": 8},
        )
        assert rep.status_code == 200
        body = rep.json()
        assert body["scope"]["project_id"] == project_id
        assert body["totals"]["assignee_count"] >= 2
        by_name = {x["assignee"]: x for x in body["assignees"]}
        assert "alice" in by_name
        assert by_name["alice"]["active_task_count"] == 2
        assert isinstance(by_name["alice"]["utilization_percent"], (int, float))


@pytest.mark.asyncio
async def test_resource_workload_settings_thresholds_and_trend():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        p = await ac.post(
            "/projects/",
            json={
                "name": "UT_WorkloadCfg_" + __import__("uuid").uuid4().hex[:8],
                "tasks": [
                    {"name": "A", "assigned_to": "alice", "status": "In Progress", "duration_days": 10},
                    {"name": "B", "assigned_to": "bob", "status": "In Progress", "duration_days": 1},
                ],
            },
        )
        assert p.status_code == 201
        project_id = p.json()["id"]

        role_set = await ac.put("/reports/workload/settings/roles/dev", params={"capacity_hours_per_day": 6})
        assert role_set.status_code == 200
        assignee_set = await ac.put(
            "/reports/workload/settings/assignees/alice",
            params={"capacity_hours_per_day": 4, "role": "dev"},
        )
        assert assignee_set.status_code == 200

        rep = await ac.get(
            "/reports/workload",
            params={
                "project_id": project_id,
                "window_days": 7,
                "capacity_hours_per_day": 8,
                "overalloc_threshold_percent": 90,
                "underalloc_threshold_percent": 30,
            },
        )
        assert rep.status_code == 200
        rows = {r["assignee"]: r for r in rep.json()["assignees"]}
        assert rows["alice"]["capacity_hours_per_day"] == 4
        assert rows["alice"]["role"] == "dev"
        assert rows["alice"]["allocation_status"] in ("overallocated", "balanced", "underallocated")

        trend = await ac.get("/reports/workload/trend", params={"project_id": project_id, "weeks": 4})
        assert trend.status_code == 200
        assert len(trend.json()["points"]) == 4


@pytest.mark.asyncio
async def test_formula_depth_functions_and_governance_depth():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        p = await ac.post(
            "/projects/",
            json={
                "name": "UT_FormulaGovDepth_" + __import__("uuid").uuid4().hex[:8],
                "tasks": [{"name": "T1", "percent_complete": 40, "duration_days": 4, "status": "Not Started"}],
            },
        )
        assert p.status_code == 201
        project_id = p.json()["id"]
        task_id = (await ac.get("/tasks/", params={"project_id": project_id})).json()[0]["id"]

        # Deeper governance policy.
        gov = await ac.patch(
            f"/projects/{project_id}/governance",
            json={
                "locked_fields": ["status"],
                "restrict_locked_to_admin": True,
                "required_fields": ["assigned_to"],
                "allowed_statuses": ["Not Started", "In Progress", "Complete"],
                "edit_window_days": None,
            },
        )
        assert gov.status_code == 200
        assert "assigned_to" in gov.json()["required_fields"]

        blocked_required = await ac.patch(
            f"/tasks/{task_id}",
            json={"description": "x"},
            headers={"x-user-role": "editor", "x-user-name": "alice"},
        )
        assert blocked_required.status_code == 400

        ok_required = await ac.patch(
            f"/tasks/{task_id}",
            json={"assigned_to": "alice"},
            headers={"x-user-role": "editor", "x-user-name": "alice"},
        )
        assert ok_required.status_code == 200

        blocked_status = await ac.patch(
            f"/tasks/{task_id}",
            json={"status": "Blocked"},
            headers={"x-user-role": "admin", "x-user-name": "admin"},
        )
        assert blocked_status.status_code == 400

        # Formula function depth.
        formulas = await ac.patch(
            f"/projects/{project_id}/formulas",
            json=[
                {
                    "name": "Math",
                    "target_field": "duration_days",
                    "expression": "MAX(3, percent_complete/10) + IF(percent_complete > 20, 1, 0)",
                    "enabled": True,
                }
            ],
        )
        assert formulas.status_code == 200

        ev = await ac.post(f"/projects/{project_id}/formulas/evaluate")
        assert ev.status_code == 200
        refreshed = await ac.get(f"/tasks/{task_id}")
        assert refreshed.status_code == 200
        assert refreshed.json()["duration_days"] >= 3


@pytest.mark.asyncio
async def test_templates_catalog_and_solution_set_project_creation():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        cat = await ac.get("/template/catalog")
        assert cat.status_code == 200
        assert len(cat.json()) >= 2
        template_id = cat.json()[0]["id"]

        create_one = await ac.post(
            f"/template/catalog/{template_id}/create-project",
            json={"name": "UT_TemplateOne_" + __import__("uuid").uuid4().hex[:8]},
        )
        assert create_one.status_code == 200
        project_id = create_one.json()["project"]["id"]

        tasks = await ac.get("/tasks/", params={"project_id": project_id})
        assert tasks.status_code == 200
        assert len(tasks.json()) >= 1

        sets = await ac.get("/template/solution-sets")
        assert sets.status_code == 200
        sid = sets.json()[0]["id"]
        create_set = await ac.post(
            f"/template/solution-sets/{sid}/create-projects",
            json={"name_prefix": "UT_Set_" + __import__("uuid").uuid4().hex[:6]},
        )
        assert create_set.status_code == 200
        assert len(create_set.json()["created_projects"]) >= 1


@pytest.mark.asyncio
async def test_collaboration_notifications_mentions_assignment_and_inbox():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        p = await ac.post(
            "/projects/",
            json={
                "name": "UT_CollabNotify_" + __import__("uuid").uuid4().hex[:8],
                "tasks": [{"name": "Task1", "assigned_to": "alice"}],
            },
        )
        assert p.status_code == 201
        project_id = p.json()["id"]
        task_id = (await ac.get("/tasks/", params={"project_id": project_id})).json()[0]["id"]

        # Assignment notification (create path)
        inbox_alice = await ac.get("/alerts/inbox", params={"user_name": "alice"})
        assert inbox_alice.status_code == 200
        assert any(a.get("kind") == "task_assigned" for a in inbox_alice.json())

        # Mention notification
        c = await ac.post(
            f"/comments/?project_id={project_id}",
            json={"task_id": task_id, "author": "bob", "body": "Please check this @alice and @charlie"},
        )
        assert c.status_code == 201

        inbox_alice_2 = await ac.get("/alerts/inbox", params={"user_name": "alice"})
        assert any(a.get("kind") == "comment_mention" for a in inbox_alice_2.json())
        inbox_charlie = await ac.get("/alerts/inbox", params={"user_name": "charlie"})
        assert any(a.get("kind") == "comment_mention" for a in inbox_charlie.json())

        # Sharing notification
        up = await ac.patch(
            f"/projects/{project_id}",
            json={"shares": [{"email": "viewer@example.com", "role": "viewer"}]},
        )
        assert up.status_code == 200
        inbox_viewer = await ac.get("/alerts/inbox", params={"user_name": "viewer@example.com"})
        assert any(a.get("kind") == "share_added" for a in inbox_viewer.json())


@pytest.mark.asyncio
async def test_jira_integration_test_and_import_with_mock_issues():
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        p = await ac.post(
            "/projects/",
            json={"name": "UT_Jira_" + __import__("uuid").uuid4().hex[:8], "tasks": [{"name": "Seed"}]},
        )
        assert p.status_code == 201
        project_id = p.json()["id"]

        cfg = await ac.patch(
            f"/projects/{project_id}/integrations",
            json={
                "integrations": [
                    {
                        "type": "jira",
                        "enabled": True,
                        "endpoint": "https://example.atlassian.net",
                        "secret": "token",
                        "settings": {
                            "jira_email": "jira-user@example.com",
                            "jira_jql": "project = DEMO ORDER BY updated DESC",
                            "mock_issues": [
                                {
                                    "key": "DEMO-1",
                                    "fields": {
                                        "summary": "Issue one",
                                        "description": "Imported from Jira",
                                        "status": {"name": "In Progress"},
                                    },
                                },
                                {
                                    "key": "DEMO-2",
                                    "fields": {
                                        "summary": "Issue two",
                                        "status": {"name": "Done"},
                                    },
                                },
                            ],
                        },
                    }
                ]
            },
        )
        assert cfg.status_code == 200

        test_conn = await ac.post(
            f"/projects/{project_id}/integrations/test",
            json={"integration_type": "jira", "event_type": "manual_test"},
        )
        assert test_conn.status_code == 200

        imp = await ac.post(
            f"/projects/{project_id}/integrations/jira/import",
            json={"jql": "project=DEMO", "max_results": 10},
        )
        assert imp.status_code == 200
        assert imp.json()["created"] >= 2

        tasks = await ac.get("/tasks/", params={"project_id": project_id})
        assert tasks.status_code == 200
        names = {t["name"] for t in tasks.json()}
        assert "Issue one" in names
        assert "Issue two" in names

