import re
from datetime import datetime
from typing import Iterable


MENTION_RE = re.compile(r"@([A-Za-z0-9_.-]{2,64})")


def extract_mentions(text: str) -> list[str]:
    names = {m.group(1).strip() for m in MENTION_RE.finditer(text or "") if m.group(1).strip()}
    return sorted(names)


async def create_user_notification(
    db,
    *,
    project_id: str,
    task_id: str | None,
    recipient_user: str,
    title: str,
    message: str,
    kind: str,
    severity: str = "info",
    dedupe_key: dict | None = None,
) -> bool:
    """
    Create a targeted in-app alert for a recipient user.
    Returns True when inserted, False when deduped.
    """
    recipient = (recipient_user or "").strip()
    if not recipient:
        return False

    if dedupe_key:
        q = {"project_id": project_id, "recipient_user": recipient, "kind": kind}
        q.update(dedupe_key)
        exists = await db["alerts"].find_one(q)
        if exists:
            return False

    await db["alerts"].insert_one(
        {
            "project_id": project_id,
            "task_id": task_id,
            "title": title[:200],
            "message": message[:2000],
            "severity": severity,
            "read": False,
            "kind": kind,
            "recipient_user": recipient,
            "created_at": datetime.utcnow(),
        }
    )
    return True


async def create_bulk_user_notifications(
    db,
    *,
    project_id: str,
    task_id: str | None,
    recipients: Iterable[str],
    title: str,
    message: str,
    kind: str,
    severity: str = "info",
) -> int:
    created = 0
    for user in recipients:
        ok = await create_user_notification(
            db,
            project_id=project_id,
            task_id=task_id,
            recipient_user=user,
            title=title,
            message=message,
            kind=kind,
            severity=severity,
        )
        if ok:
            created += 1
    return created

