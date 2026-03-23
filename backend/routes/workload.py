from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from db import get_database


router = APIRouter()
SETTINGS_KEY = "default"


def _to_date(val):
    if val is None:
        return None
    if hasattr(val, "date"):
        return val.date()
    return None


def _duration_days(task: dict) -> int:
    explicit = task.get("duration_days")
    if isinstance(explicit, int) and explicit > 0:
        return explicit
    start = _to_date(task.get("start_date"))
    end = _to_date(task.get("end_date"))
    if start and end and end >= start:
        return (end - start).days + 1
    return 1


def _window_overlap_days(task: dict, window_start, window_end) -> int:
    start = _to_date(task.get("start_date"))
    end = _to_date(task.get("end_date"))
    if not start and not end:
        # No schedule data; count as one-day unscheduled load.
        return 1
    if start and not end:
        end = start
    if end and not start:
        start = end
    if not start or not end:
        return 0
    a = max(start, window_start)
    b = min(end, window_end)
    if b < a:
        return 0
    return (b - a).days + 1


def _norm_key(s: str) -> str:
    return str(s or "").strip().lower()


async def _get_settings(db) -> dict:
    doc = await db["workload_settings"].find_one({"_id": SETTINGS_KEY})
    if not doc:
        return {
            "_id": SETTINGS_KEY,
            "assignee_capacity_per_day": {},
            "role_capacity_per_day": {},
            "assignee_roles": {},
            "updated_at": datetime.utcnow(),
        }
    doc.setdefault("assignee_capacity_per_day", {})
    doc.setdefault("role_capacity_per_day", {})
    doc.setdefault("assignee_roles", {})
    return doc


async def _upsert_settings(db, updates: dict) -> None:
    updates["updated_at"] = datetime.utcnow()
    await db["workload_settings"].update_one({"_id": SETTINGS_KEY}, {"$set": updates}, upsert=True)


def _capacity_for_assignee(settings: dict, assignee: str, fallback: int) -> tuple[int, Optional[str]]:
    assignee_k = _norm_key(assignee)
    a_map = settings.get("assignee_capacity_per_day") or {}
    r_map = settings.get("role_capacity_per_day") or {}
    ar_map = settings.get("assignee_roles") or {}
    if assignee_k in a_map:
        return int(a_map[assignee_k]), ar_map.get(assignee_k)
    role = ar_map.get(assignee_k)
    if role and role in r_map:
        return int(r_map[role]), role
    return int(fallback), role


def _build_assignee_rows(
    task_docs: List[dict],
    window_start,
    window_end,
    window_days: int,
    fallback_capacity_per_day: int,
    settings: dict,
    overalloc_threshold_percent: int,
    underalloc_threshold_percent: int,
) -> List[dict]:
    today = datetime.now(timezone.utc).date()
    by_assignee: Dict[str, dict] = {}

    for t in task_docs:
        owner = str(t.get("assigned_to") or "").strip()
        if not owner:
            continue
        capacity_per_day, role = _capacity_for_assignee(settings, owner, fallback_capacity_per_day)
        row = by_assignee.setdefault(
            owner,
            {
                "assignee": owner,
                "role": role,
                "capacity_hours_per_day": capacity_per_day,
                "active_task_count": 0,
                "overdue_task_count": 0,
                "scheduled_task_count": 0,
                "unscheduled_task_count": 0,
                "load_hours": 0,
                "capacity_hours": window_days * capacity_per_day,
                "utilization_percent": 0.0,
                "overallocated": False,
                "underallocated": False,
                "allocation_status": "balanced",
                "task_ids": [],
            },
        )
        row["active_task_count"] += 1
        row["task_ids"].append(str(t["_id"]))

        end_d = _to_date(t.get("end_date"))
        if end_d and end_d < today:
            row["overdue_task_count"] += 1

        if _to_date(t.get("start_date")) or _to_date(t.get("end_date")):
            row["scheduled_task_count"] += 1
        else:
            row["unscheduled_task_count"] += 1

        overlap_days = _window_overlap_days(t, window_start, window_end)
        if not (_to_date(t.get("start_date")) or _to_date(t.get("end_date"))):
            overlap_days = min(_duration_days(t), window_days)
        row["load_hours"] += overlap_days * capacity_per_day

    items = list(by_assignee.values())
    for row in items:
        cap = row["capacity_hours"] or 1
        util = (row["load_hours"] / cap) * 100.0
        row["utilization_percent"] = round(util, 1)
        row["overallocated"] = util > overalloc_threshold_percent
        row["underallocated"] = util < underalloc_threshold_percent
        if row["overallocated"]:
            row["allocation_status"] = "overallocated"
        elif row["underallocated"]:
            row["allocation_status"] = "underallocated"
        else:
            row["allocation_status"] = "balanced"
        row["task_ids"] = sorted(row["task_ids"])
    items.sort(key=lambda x: (x["overallocated"], x["utilization_percent"]), reverse=True)
    return items


@router.get("/workload")
async def workload_report(
    project_id: str = Query(default=""),
    window_days: int = Query(default=14, ge=1, le=90),
    capacity_hours_per_day: int = Query(default=8, ge=1, le=24),
    overalloc_threshold_percent: int = Query(default=100, ge=50, le=300),
    underalloc_threshold_percent: int = Query(default=60, ge=0, le=100),
) -> dict:
    """
    Resource/workload snapshot.
    - Aggregates active (non-complete) assigned tasks per assignee.
    - Calculates forecast load in the look-ahead window and flags over-allocation.
    """
    db = get_database()
    q: dict = {"status": {"$ne": "Complete"}, "assigned_to": {"$nin": [None, ""]}}
    projects_filter: Optional[List[str]] = None

    if project_id:
        try:
            oid = ObjectId(project_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid project id")
        p = await db["projects"].find_one({"_id": oid})
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")
        projects_filter = [project_id]
        q["project_id"] = project_id
    else:
        projects_filter = []
        async for p in db["projects"].find({}, {"_id": 1}):
            projects_filter.append(str(p["_id"]))

    settings = await _get_settings(db)
    today = datetime.now(timezone.utc).date()
    window_start = today
    window_end = today + timedelta(days=window_days - 1)

    task_docs = []
    async for t in db["tasks"].find(q):
        task_docs.append(t)
    items = _build_assignee_rows(
        task_docs,
        window_start=window_start,
        window_end=window_end,
        window_days=window_days,
        fallback_capacity_per_day=capacity_hours_per_day,
        settings=settings,
        overalloc_threshold_percent=overalloc_threshold_percent,
        underalloc_threshold_percent=underalloc_threshold_percent,
    )

    return {
        "scope": {
            "project_id": project_id or None,
            "project_count": len(projects_filter or []),
            "window_days": window_days,
            "capacity_hours_per_day": capacity_hours_per_day,
            "overalloc_threshold_percent": overalloc_threshold_percent,
            "underalloc_threshold_percent": underalloc_threshold_percent,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        },
        "totals": {
            "assignee_count": len(items),
            "active_task_count": sum(i["active_task_count"] for i in items),
            "overdue_task_count": sum(i["overdue_task_count"] for i in items),
            "overallocated_count": sum(1 for i in items if i["overallocated"]),
            "underallocated_count": sum(1 for i in items if i["underallocated"]),
        },
        "assignees": items,
    }


@router.get("/workload/settings")
async def get_workload_settings() -> dict:
    db = get_database()
    settings = await _get_settings(db)
    settings.pop("_id", None)
    return settings


@router.put("/workload/settings/assignees/{assignee}")
async def upsert_assignee_capacity(
    assignee: str,
    capacity_hours_per_day: int = Query(..., ge=1, le=24),
    role: str = Query(default=""),
) -> dict:
    db = get_database()
    settings = await _get_settings(db)
    key = _norm_key(assignee)
    if not key:
        raise HTTPException(status_code=400, detail="Invalid assignee")
    a_map = settings.get("assignee_capacity_per_day") or {}
    r_map = settings.get("assignee_roles") or {}
    a_map[key] = int(capacity_hours_per_day)
    if role.strip():
        r_map[key] = _norm_key(role)
    await _upsert_settings(db, {"assignee_capacity_per_day": a_map, "assignee_roles": r_map})
    return {"status": "ok"}


@router.delete("/workload/settings/assignees/{assignee}")
async def delete_assignee_capacity(assignee: str) -> dict:
    db = get_database()
    settings = await _get_settings(db)
    key = _norm_key(assignee)
    a_map = settings.get("assignee_capacity_per_day") or {}
    r_map = settings.get("assignee_roles") or {}
    a_map.pop(key, None)
    r_map.pop(key, None)
    await _upsert_settings(db, {"assignee_capacity_per_day": a_map, "assignee_roles": r_map})
    return {"status": "ok"}


@router.put("/workload/settings/roles/{role}")
async def upsert_role_capacity(role: str, capacity_hours_per_day: int = Query(..., ge=1, le=24)) -> dict:
    db = get_database()
    settings = await _get_settings(db)
    key = _norm_key(role)
    if not key:
        raise HTTPException(status_code=400, detail="Invalid role")
    rc = settings.get("role_capacity_per_day") or {}
    rc[key] = int(capacity_hours_per_day)
    await _upsert_settings(db, {"role_capacity_per_day": rc})
    return {"status": "ok"}


@router.delete("/workload/settings/roles/{role}")
async def delete_role_capacity(role: str) -> dict:
    db = get_database()
    settings = await _get_settings(db)
    key = _norm_key(role)
    rc = settings.get("role_capacity_per_day") or {}
    rc.pop(key, None)
    await _upsert_settings(db, {"role_capacity_per_day": rc})
    return {"status": "ok"}


@router.get("/workload/trend")
async def workload_trend(
    project_id: str = Query(default=""),
    weeks: int = Query(default=8, ge=2, le=26),
    capacity_hours_per_day: int = Query(default=8, ge=1, le=24),
) -> dict:
    db = get_database()
    q: dict = {"status": {"$ne": "Complete"}, "assigned_to": {"$nin": [None, ""]}}
    if project_id:
        try:
            oid = ObjectId(project_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid project id")
        if not await db["projects"].find_one({"_id": oid}):
            raise HTTPException(status_code=404, detail="Project not found")
        q["project_id"] = project_id

    settings = await _get_settings(db)
    task_docs = []
    async for t in db["tasks"].find(q):
        task_docs.append(t)

    today = datetime.now(timezone.utc).date()
    start_of_week = today - timedelta(days=today.weekday())
    points = []
    for i in range(weeks):
        ws = start_of_week + timedelta(days=i * 7)
        we = ws + timedelta(days=6)
        rows = _build_assignee_rows(
            task_docs,
            window_start=ws,
            window_end=we,
            window_days=7,
            fallback_capacity_per_day=capacity_hours_per_day,
            settings=settings,
            overalloc_threshold_percent=100,
            underalloc_threshold_percent=60,
        )
        points.append(
            {
                "week_start": ws.isoformat(),
                "week_end": we.isoformat(),
                "assignee_count": len(rows),
                "avg_utilization_percent": round(
                    (sum(r["utilization_percent"] for r in rows) / len(rows)) if rows else 0.0, 1
                ),
                "overallocated_count": sum(1 for r in rows if r["overallocated"]),
                "underallocated_count": sum(1 for r in rows if r["underallocated"]),
            }
        )
    return {"project_id": project_id or None, "weeks": weeks, "points": points}

