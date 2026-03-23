from datetime import date, datetime
from typing import List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from bson import ObjectId
from pymongo.errors import PyMongoError

from db import get_database, normalize_document, apply_status_completion_rules
from models import BaselineSnapshotOut, Project, ProjectCreateWithTasks, ProjectUpdate
from storage import UPLOAD_ROOT
from notification_logic import create_user_notification


router = APIRouter()


def _as_date(val) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return None


def _as_datetime_midnight(d: Optional[date]) -> Optional[datetime]:
    if d is None:
        return None
    return datetime(d.year, d.month, d.day)


async def _task_schedule_bounds(db, project_id: str) -> Tuple[Optional[date], Optional[date]]:
    """Min start and max end across tasks (for project baseline when plan dates are empty)."""
    min_start: Optional[date] = None
    max_end: Optional[date] = None
    async for task in db["tasks"].find({"project_id": project_id}):
        sd = _as_date(task.get("start_date"))
        ed = _as_date(task.get("end_date"))
        if sd is not None and (min_start is None or sd < min_start):
            min_start = sd
        if ed is not None and (max_end is None or ed > max_end):
            max_end = ed
    return min_start, max_end


def _normalize_project_shares(doc: dict) -> None:
    """Older documents may omit shares or contain invalid entries; keep API responses valid."""
    raw = doc.get("shares")
    if not raw:
        doc["shares"] = []
        return
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        email = item.get("email")
        if not email or not str(email).strip():
            continue
        role = item.get("role") or "viewer"
        if role not in ("viewer", "editor", "admin"):
            role = "viewer"
        out.append({"email": str(email).strip(), "role": role})
    doc["shares"] = out


def _normalize_project_automations(doc: dict) -> None:
    """
    Older documents may not have `automations` or may contain partially invalid entries.
    Keep API responses valid for the `Project` model.
    """
    raw = doc.get("automations")
    default = [
        {"type": "notify_on_completion", "enabled": True},
        {"type": "overdue_alert", "enabled": True},
    ]
    if not raw:
        doc["automations"] = default
        return

    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        t = item.get("type")
        if t not in ("notify_on_completion", "overdue_alert"):
            continue
        enabled = item.get("enabled", True)
        out.append({"type": t, "enabled": bool(enabled)})

    # If user stored only one rule, keep the other at its default enabled value.
    if not out:
        doc["automations"] = default
        return

    have = {x["type"] for x in out}
    for d in default:
        if d["type"] not in have:
            out.append(d)
    doc["automations"] = out


def _normalize_project_formulas(doc: dict) -> None:
    raw = doc.get("formulas")
    if not raw:
        doc["formulas"] = []
        return
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        target = str(item.get("target_field") or "").strip()
        expr = str(item.get("expression") or "").strip()
        if not name or not target or not expr:
            continue
        out.append(
            {
                "name": name,
                "target_field": target,
                "expression": expr,
                "enabled": bool(item.get("enabled", True)),
            }
        )
    doc["formulas"] = out


def _normalize_project_governance(doc: dict) -> None:
    raw = doc.get("governance")
    if not isinstance(raw, dict):
        doc["governance"] = {
            "locked_fields": [],
            "restrict_locked_to_admin": True,
            "required_fields": [],
            "allowed_statuses": [],
            "edit_window_days": None,
        }
        return
    locked = raw.get("locked_fields") or []
    if not isinstance(locked, list):
        locked = []
    doc["governance"] = {
        "locked_fields": [str(x) for x in locked if str(x).strip()],
        "restrict_locked_to_admin": bool(raw.get("restrict_locked_to_admin", True)),
        "required_fields": [
            str(x).strip()
            for x in (raw.get("required_fields") or [])
            if str(x).strip()
        ],
        "allowed_statuses": [
            str(x).strip()
            for x in (raw.get("allowed_statuses") or [])
            if str(x).strip()
        ],
        "edit_window_days": int(raw["edit_window_days"])
        if isinstance(raw.get("edit_window_days"), int) and raw.get("edit_window_days") >= 0
        else None,
    }


def _normalize_project_integrations(doc: dict) -> None:
    raw = doc.get("integrations")
    if not raw:
        doc["integrations"] = []
        return
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        itype = str(item.get("type") or "").strip().lower()
        if itype not in ("webhook", "slack", "email"):
            continue
        out.append(
            {
                "type": itype,
                "enabled": bool(item.get("enabled", True)),
                "endpoint": item.get("endpoint"),
                "secret": item.get("secret"),
                "settings": item.get("settings") if isinstance(item.get("settings"), dict) else {},
            }
        )
    doc["integrations"] = out


def _serialize_project(doc: dict) -> Project:
    # Mongo stores document id in `_id`. Expose it as `id` for the frontend.
    _normalize_project_shares(doc)
    _normalize_project_automations(doc)
    _normalize_project_formulas(doc)
    _normalize_project_governance(doc)
    _normalize_project_integrations(doc)
    if doc.get("baseline_end") and doc.get("end_date"):
        variance = (doc["end_date"].date() - doc["baseline_end"].date()).days
        doc["baseline_variance_days"] = variance
        if variance > 0:
            doc["schedule_status"] = "Late"
        elif variance < 0:
            doc["schedule_status"] = "Ahead"
        else:
            doc["schedule_status"] = "On Baseline"
    else:
        doc["baseline_variance_days"] = None
        doc["schedule_status"] = "No Baseline"
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return Project(**doc)


@router.get("/", response_model=List[Project])
async def list_projects() -> List[Project]:
    db = get_database()
    projects = []
    async for doc in db["projects"].find():
        projects.append(_serialize_project(doc))
    return projects


@router.post("/", response_model=Project, status_code=201)
async def create_project(payload: ProjectCreateWithTasks) -> Project:
    db = get_database()
    now = datetime.utcnow()
    payload_data = payload.model_dump()
    tasks = payload_data.pop("tasks")
    doc = normalize_document(payload_data)
    doc.setdefault("shares", [])
    doc.setdefault("formulas", [])
    doc.setdefault(
        "governance",
        {
            "locked_fields": [],
            "restrict_locked_to_admin": True,
            "required_fields": [],
            "allowed_statuses": [],
            "edit_window_days": None,
        },
    )
    doc.setdefault("integrations", [])
    doc.update({"created_at": now, "updated_at": now})
    try:
        existing = await db["projects"].find_one({"name": payload.name})
        if existing:
            raise HTTPException(status_code=409, detail="Project name already exists")
        result = await db["projects"].insert_one(doc)
        project_id = str(result.inserted_id)

        task_docs = []
        for t in tasks:
            task_docs.append(
                {
                    **apply_status_completion_rules(normalize_document(t)),
                    "project_id": project_id,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        try:
            await db["tasks"].insert_many(task_docs)
        except PyMongoError:
            # Best-effort rollback (transactions require replica set).
            await db["projects"].delete_one({"_id": result.inserted_id})
            raise

        # Collaboration notifications: initial task assignment alerts.
        try:
            async for tdoc in db["tasks"].find({"project_id": project_id}):
                assignee = tdoc.get("assigned_to")
                if assignee:
                    await create_user_notification(
                        db,
                        project_id=project_id,
                        task_id=str(tdoc["_id"]),
                        recipient_user=str(assignee),
                        title="Task assigned",
                        message=f'You were assigned task "{tdoc.get("name", "Task")}".',
                        kind="task_assigned",
                        dedupe_key={"task_id": str(tdoc["_id"])},
                    )
        except Exception:
            pass

        created = await db["projects"].find_one({"_id": result.inserted_id})
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e.__class__.__name__}")
    return _serialize_project(created)


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str) -> Project:
    db = get_database()
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")
    doc = await db["projects"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    return _serialize_project(doc)


@router.patch("/{project_id}", response_model=Project)
async def update_project(project_id: str, payload: ProjectUpdate) -> Project:
    db = get_database()
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")
    updates = normalize_document({k: v for k, v in payload.model_dump(exclude_unset=True).items()})
    if not updates:
        doc = await db["projects"].find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Project not found")
        return _serialize_project(doc)
    updates["updated_at"] = datetime.utcnow()
    old_doc = await db["projects"].find_one({"_id": oid}) or {}
    result = await db["projects"].find_one_and_update(
        {"_id": oid},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")

    # Collaboration notifications: sharing updates can notify recipients.
    try:
        if "shares" in updates:
            old_shares = old_doc.get("shares") or []
            old_emails = {str(s.get("email", "")).strip().lower() for s in old_shares if isinstance(s, dict)}
            new_shares = result.get("shares") or []
            for s in new_shares:
                if not isinstance(s, dict):
                    continue
                email = str(s.get("email", "")).strip()
                if not email:
                    continue
                role = str(s.get("role") or "viewer")
                if email.lower() not in old_emails:
                    await create_user_notification(
                        db,
                        project_id=project_id,
                        task_id=None,
                        recipient_user=email,
                        title="Project shared with you",
                        message=f'You were added to project "{result.get("name", "Project")}" as {role}.',
                        kind="share_added",
                        dedupe_key={"recipient_user": email, "message": f'You were added to project "{result.get("name", "Project")}" as {role}.'},
                    )
    except Exception:
        pass
    return _serialize_project(result)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str) -> None:
    db = get_database()
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")
    async for att in db["attachments"].find({"project_id": project_id}):
        rel = att.get("disk_relative")
        if rel:
            path = UPLOAD_ROOT / rel
            try:
                if path.is_file():
                    path.unlink()
                parent = path.parent
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass
    await db["attachments"].delete_many({"project_id": project_id})
    await db["comments"].delete_many({"project_id": project_id})
    await db["alerts"].delete_many({"project_id": project_id})
    await db["tasks"].delete_many({"project_id": project_id})
    await db["projects"].delete_one({"_id": oid})
    return None


@router.post("/{project_id}/baseline/snapshot", response_model=BaselineSnapshotOut)
async def snapshot_project_baseline(project_id: str) -> BaselineSnapshotOut:
    db = get_database()
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")

    project = await db["projects"].find_one({"_id": oid})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    now = datetime.utcnow()

    # Project-level baseline: use project dates, or roll up from tasks when plan dates are unset.
    proj_start = project.get("start_date")
    proj_end = project.get("end_date")
    t_min, t_max = await _task_schedule_bounds(db, project_id)
    if proj_start is None and t_min is not None:
        proj_start = _as_datetime_midnight(t_min)
    if proj_end is None and t_max is not None:
        proj_end = _as_datetime_midnight(t_max)

    await db["projects"].update_one(
        {"_id": oid},
        {
            "$set": {
                "baseline_start": proj_start,
                "baseline_end": proj_end,
                "updated_at": now,
            }
        },
    )

    cursor = db["tasks"].find({"project_id": project_id})
    updated_tasks = 0
    async for task in cursor:
        ts = task.get("start_date")
        te = task.get("end_date")
        await db["tasks"].update_one(
            {"_id": task["_id"]},
            {
                "$set": {
                    "baseline_start": ts,
                    "baseline_end": te,
                    "updated_at": now,
                }
            },
        )
        updated_tasks += 1

    updated = await db["projects"].find_one({"_id": oid})
    if not updated:
        raise HTTPException(status_code=500, detail="Project missing after baseline snapshot")
    return BaselineSnapshotOut(
        status="ok",
        updated_tasks=updated_tasks,
        project=_serialize_project(updated),
    )

