from datetime import datetime, timezone
from typing import Dict, List

from bson import ObjectId
from fastapi import APIRouter, HTTPException

from db import get_database


router = APIRouter()


def _to_date(val):
    if val is None:
        return None
    if hasattr(val, "date"):
        return val.date()
    return None


def _project_status_bucket(status: str) -> str:
    if status in ("On Track", "At Risk", "Off Track"):
        return status
    return "Other"


@router.get("/portfolio")
async def portfolio_report() -> dict:
    """
    Portfolio rollup across all projects.
    """
    db = get_database()
    today = datetime.now(timezone.utc).date()

    projects: List[dict] = []
    async for p in db["projects"].find():
        projects.append(p)

    total_projects = len(projects)
    project_status_breakdown: Dict[str, int] = {"On Track": 0, "At Risk": 0, "Off Track": 0, "Other": 0}
    for p in projects:
        project_status_breakdown[_project_status_bucket(p.get("status", "Other"))] += 1

    total_tasks = 0
    completed_tasks = 0
    overdue_tasks = 0
    critical_tasks = 0
    total_percent = 0
    with_percent = 0

    project_rows = []
    for p in projects:
        pid = str(p["_id"])
        task_docs: List[dict] = []
        async for t in db["tasks"].find({"project_id": pid}):
            task_docs.append(t)

        p_total = len(task_docs)
        p_completed = 0
        p_overdue = 0
        p_percent_sum = 0
        p_with_percent = 0

        for t in task_docs:
            status = t.get("status")
            if status == "Complete":
                p_completed += 1
            ed = _to_date(t.get("end_date"))
            if ed is not None and ed < today and status != "Complete":
                p_overdue += 1
            pct = t.get("percent_complete")
            if isinstance(pct, (int, float)):
                p_percent_sum += float(pct)
                p_with_percent += 1
            if t.get("is_critical") is True:
                critical_tasks += 1

        total_tasks += p_total
        completed_tasks += p_completed
        overdue_tasks += p_overdue
        total_percent += p_percent_sum
        with_percent += p_with_percent

        completion_rate = (p_completed / p_total * 100) if p_total else 0
        avg_percent = (p_percent_sum / p_with_percent) if p_with_percent else 0
        project_rows.append(
            {
                "project_id": pid,
                "project_name": p.get("name", "Unnamed"),
                "status": p.get("status", "Other"),
                "task_count": p_total,
                "completed_task_count": p_completed,
                "overdue_task_count": p_overdue,
                "completion_rate": round(completion_rate, 1),
                "avg_percent_complete": round(avg_percent, 1),
            }
        )

    portfolio_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks else 0
    portfolio_avg_percent = (total_percent / with_percent) if with_percent else 0

    return {
        "totals": {
            "project_count": total_projects,
            "task_count": total_tasks,
            "completed_task_count": completed_tasks,
            "overdue_task_count": overdue_tasks,
            "critical_task_count": critical_tasks,
            "completion_rate": round(portfolio_completion_rate, 1),
            "avg_percent_complete": round(portfolio_avg_percent, 1),
        },
        "project_status_breakdown": project_status_breakdown,
        "projects": sorted(project_rows, key=lambda x: x["project_name"].lower()),
    }


@router.get("/projects/{project_id}")
async def project_report(project_id: str) -> dict:
    """
    Single-project reporting details for dashboard drill-down.
    """
    db = get_database()
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")

    p = await db["projects"].find_one({"_id": oid})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    today = datetime.now(timezone.utc).date()
    task_docs: List[dict] = []
    async for t in db["tasks"].find({"project_id": project_id}):
        task_docs.append(t)

    total = len(task_docs)
    completed = 0
    overdue = 0
    status_counts: Dict[str, int] = {"Not Started": 0, "In Progress": 0, "Blocked": 0, "Complete": 0, "Other": 0}
    critical = 0
    for t in task_docs:
        status = t.get("status", "Other")
        if status not in status_counts:
            status = "Other"
        status_counts[status] += 1
        if status == "Complete":
            completed += 1
        ed = _to_date(t.get("end_date"))
        if ed is not None and ed < today and t.get("status") != "Complete":
            overdue += 1
        if t.get("is_critical") is True:
            critical += 1

    return {
        "project": {
            "id": str(p["_id"]),
            "name": p.get("name", "Unnamed"),
            "status": p.get("status", "Other"),
        },
        "totals": {
            "task_count": total,
            "completed_task_count": completed,
            "overdue_task_count": overdue,
            "critical_task_count": critical,
            "completion_rate": round((completed / total * 100) if total else 0, 1),
        },
        "task_status_breakdown": status_counts,
    }

