from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException
from bson import ObjectId
from pydantic import BaseModel, Field

from automation_logic import is_automation_enabled, scan_completed_alerts, scan_overdue_alerts
from db import get_database
from models import AutomationRule


router = APIRouter()


class AutomationsPatch(BaseModel):
    automations: List[AutomationRule] = Field(default_factory=list)


DEFAULT_AUTOMATIONS = [
    {"type": "notify_on_completion", "enabled": True},
    {"type": "overdue_alert", "enabled": True},
]


def _effective_automations(project_doc: dict) -> List[dict]:
    raw = project_doc.get("automations")
    if not raw:
        return DEFAULT_AUTOMATIONS.copy()

    out: list[dict] = []
    for item in raw:
        if isinstance(item, dict) and item.get("type") in ("notify_on_completion", "overdue_alert"):
            out.append({"type": item.get("type"), "enabled": bool(item.get("enabled", True))})

    # Merge with defaults so missing rules are still present.
    have = {x["type"] for x in out}
    for d in DEFAULT_AUTOMATIONS:
        if d["type"] not in have:
            out.append(d)
    return out


@router.get("/{project_id}/automations", response_model=List[AutomationRule])
async def get_project_automations(project_id: str) -> List[AutomationRule]:
    db = get_database()
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")

    doc = await db["projects"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")

    effective = _effective_automations(doc)
    return [AutomationRule(**x) for x in effective]


@router.patch("/{project_id}/automations", response_model=List[AutomationRule])
async def patch_project_automations(project_id: str, payload: AutomationsPatch) -> List[AutomationRule]:
    db = get_database()
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")

    project = await db["projects"].find_one({"_id": oid})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    normalized = []
    allowed = {"notify_on_completion", "overdue_alert"}
    for rule in payload.automations:
        if rule.type in allowed:
            normalized.append({"type": rule.type, "enabled": bool(rule.enabled)})

    # Always keep both rule types so UI doesn't get out of sync.
    have = {x["type"] for x in normalized}
    for d in DEFAULT_AUTOMATIONS:
        if d["type"] not in have:
            normalized.append(d)

    await db["projects"].update_one({"_id": oid}, {"$set": {"automations": normalized}})
    return [AutomationRule(**x) for x in normalized]


@router.post("/{project_id}/automations/run", response_model=dict)
async def run_project_automations(project_id: str) -> dict:
    db = get_database()
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")

    project = await db["projects"].find_one({"_id": oid})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    overdue_created = 0
    completed_created = 0

    if is_automation_enabled(project, "overdue_alert"):
        overdue_created = await scan_overdue_alerts(db, project_id)

    if is_automation_enabled(project, "notify_on_completion"):
        completed_created = await scan_completed_alerts(db, project_id)

    return {
        "status": "ok",
        "overdue_alerts_created": overdue_created,
        "completion_alerts_created": completed_created,
    }

