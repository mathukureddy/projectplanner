from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from integration_events import emit_integration_events

TASK_OVERDUE_KIND = "task_overdue"
TASK_COMPLETED_KIND = "task_completed"

KNOWN_AUTOMATION_TYPES = ("notify_on_completion", "overdue_alert")


def end_date_to_date(end_val: Any) -> Optional[Any]:
    """
    Tasks store dates as `datetime` (midnight, normalized in db.py) rather than `datetime.date`.
    This helper converts anything BSON-safe back to a date.
    """
    if end_val is None:
        return None
    if hasattr(end_val, "date"):
        return end_val.date()
    return None


def is_automation_enabled(project_doc: dict, automation_type: str) -> bool:
    """
    If `project_doc.automations` is missing (older projects), default to enabled.
    """
    if automation_type not in KNOWN_AUTOMATION_TYPES:
        return False

    rules = project_doc.get("automations")
    if not rules:
        return True

    for rule in rules:
        if isinstance(rule, dict) and rule.get("type") == automation_type:
            return bool(rule.get("enabled", True))
    return True


async def scan_overdue_alerts(db, project_id: str) -> int:
    """
    Time-based trigger: create overdue alerts for tasks whose end_date is before today
    and are not marked Complete.
    """
    today = datetime.now(timezone.utc).date()
    midnight = datetime(today.year, today.month, today.day)

    created = 0
    async for task in db["tasks"].find(
        {
            "project_id": project_id,
            "status": {"$ne": "Complete"},
            "end_date": {"$lt": midnight},
        }
    ):
        end_d = end_date_to_date(task.get("end_date"))
        if not end_d or end_d >= today:
            continue

        tid = str(task["_id"])
        exists = await db["alerts"].find_one(
            {"project_id": project_id, "task_id": tid, "kind": TASK_OVERDUE_KIND}
        )
        if exists:
            continue

        name = task.get("name", "Task")
        await db["alerts"].insert_one(
            {
                "project_id": project_id,
                "task_id": tid,
                "title": f"Overdue: {name}",
                "message": f'Task "{name}" ended on {end_d} and is not marked Complete.',
                "severity": "warning",
                "read": False,
                "kind": TASK_OVERDUE_KIND,
                "created_at": datetime.utcnow(),
            }
        )
        await emit_integration_events(
            db,
            project_id,
            event_type="overdue_alert_created",
            payload={"task_id": tid, "task_name": name, "kind": TASK_OVERDUE_KIND},
        )
        created += 1

    return created


async def scan_completed_alerts(db, project_id: str) -> int:
    """
    Automation rule: ensure completed alerts exist for tasks currently in Complete status.
    This is idempotent via kind+task dedupe.
    """
    created = 0
    async for task in db["tasks"].find({"project_id": project_id, "status": "Complete"}):
        tid = str(task["_id"])
        exists = await db["alerts"].find_one(
            {"project_id": project_id, "task_id": tid, "kind": TASK_COMPLETED_KIND}
        )
        if exists:
            continue

        name = task.get("name", "Task")
        await db["alerts"].insert_one(
            {
                "project_id": project_id,
                "task_id": tid,
                "title": f"Completed: {name}",
                "message": f'Task "{name}" was marked Complete.',
                "severity": "info",
                "read": False,
                "kind": TASK_COMPLETED_KIND,
                "created_at": datetime.utcnow(),
            }
        )
        await emit_integration_events(
            db,
            project_id,
            event_type="task_completed_alert_created",
            payload={"task_id": tid, "task_name": name, "kind": TASK_COMPLETED_KIND},
        )
        created += 1
    return created


async def scan_overdue_alerts_for_projects(db, project_ids: list[str]) -> int:
    """
    Scheduler helper: scan overdue alerts for multiple projects in one pass.
    """
    if not project_ids:
        return 0

    today = datetime.now(timezone.utc).date()
    midnight = datetime(today.year, today.month, today.day)

    created = 0
    async for task in db["tasks"].find(
        {
            "project_id": {"$in": project_ids},
            "status": {"$ne": "Complete"},
            "end_date": {"$lt": midnight},
        }
    ):
        end_d = end_date_to_date(task.get("end_date"))
        if not end_d or end_d >= today:
            continue

        project_id = task.get("project_id")
        tid = str(task["_id"])
        exists = await db["alerts"].find_one(
            {"project_id": project_id, "task_id": tid, "kind": TASK_OVERDUE_KIND}
        )
        if exists:
            continue

        name = task.get("name", "Task")
        await db["alerts"].insert_one(
            {
                "project_id": project_id,
                "task_id": tid,
                "title": f"Overdue: {name}",
                "message": f'Task "{name}" ended on {end_d} and is not marked Complete.',
                "severity": "warning",
                "read": False,
                "kind": TASK_OVERDUE_KIND,
                "created_at": datetime.utcnow(),
            }
        )
        await emit_integration_events(
            db,
            project_id,
            event_type="overdue_alert_created",
            payload={"task_id": tid, "task_name": name, "kind": TASK_OVERDUE_KIND},
        )
        created += 1

    return created

