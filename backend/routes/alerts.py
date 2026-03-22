from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pymongo.errors import PyMongoError

from db import get_database
from models import Alert, AlertReadPatch, UserAlertCreate
from integration_events import emit_integration_events

router = APIRouter()


def _serialize_alert(doc: dict) -> Alert:
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return Alert(**doc)


async def _project_exists(db, project_id: str) -> bool:
    try:
        oid = ObjectId(project_id)
    except Exception:
        return False
    return await db["projects"].find_one({"_id": oid}) is not None


@router.get("/", response_model=list[Alert])
async def list_alerts(
    project_id: str = Query(...),
    unread_only: bool = Query(False),
) -> list[Alert]:
    db = get_database()
    if not await _project_exists(db, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    q: dict = {"project_id": project_id}
    if unread_only:
        q["read"] = False
    out: list[Alert] = []
    async for doc in db["alerts"].find(q).sort("created_at", -1).limit(200):
        out.append(_serialize_alert(doc))
    return out


@router.patch("/{alert_id}", response_model=Alert)
async def patch_alert(alert_id: str, payload: AlertReadPatch, project_id: str = Query(...)) -> Alert:
    db = get_database()
    try:
        oid = ObjectId(alert_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid alert id")
    updates = {"read": payload.read}
    result = await db["alerts"].find_one_and_update(
        {"_id": oid, "project_id": project_id},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _serialize_alert(result)


@router.post("/", response_model=Alert, status_code=201)
async def create_user_alert(payload: UserAlertCreate) -> Alert:
    """Manual alert (e.g. future automation hooks)."""
    db = get_database()
    project_id = payload.project_id
    if not await _project_exists(db, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    task_id = payload.task_id
    if task_id:
        try:
            tid = ObjectId(task_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid task id")
        t = await db["tasks"].find_one({"_id": tid, "project_id": project_id})
        if not t:
            raise HTTPException(status_code=404, detail="Task not found in this project")
    now = datetime.utcnow()
    doc = {
        "project_id": project_id,
        "task_id": task_id,
        "title": payload.title,
        "message": payload.message,
        "severity": "info",
        "read": False,
        "kind": "user",
        "created_at": now,
    }
    try:
        result = await db["alerts"].insert_one(doc)
        created = await db["alerts"].find_one({"_id": result.inserted_id})
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e.__class__.__name__}")
    return _serialize_alert(created)


def _task_end_date_as_date(end_val):
    if end_val is None:
        return None
    if hasattr(end_val, "date"):
        return end_val.date()
    return end_val


@router.post("/scan-overdue", response_model=dict)
async def scan_overdue_tasks(project_id: str = Query(...)) -> dict:
    """
    Create alerts for tasks past end_date that are not Complete.
    Dedupe per task+kind across both read/unread to avoid repeated alerts.
    """
    db = get_database()
    if not await _project_exists(db, project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    today = datetime.now(timezone.utc).date()
    created = 0
    async for task in db["tasks"].find({"project_id": project_id}):
        if (task.get("status") or "") == "Complete":
            continue
        end_d = _task_end_date_as_date(task.get("end_date"))
        if not end_d or end_d >= today:
            continue
        tid = str(task["_id"])
        exists = await db["alerts"].find_one(
            {
                "project_id": project_id,
                "task_id": tid,
                "kind": "task_overdue",
            }
        )
        if exists:
            continue
        name = task.get("name", "Task")
        doc = {
            "project_id": project_id,
            "task_id": tid,
            "title": f"Overdue: {name}",
            "message": f'Task "{name}" ended on {end_d} and is not marked Complete.',
            "severity": "warning",
            "read": False,
            "kind": "task_overdue",
            "created_at": datetime.utcnow(),
        }
        await db["alerts"].insert_one(doc)
        await emit_integration_events(
            db,
            project_id,
            event_type="overdue_alert_created",
            payload={"task_id": tid, "task_name": name, "kind": "task_overdue"},
        )
        created += 1
    return {"status": "ok", "alerts_created": created}
