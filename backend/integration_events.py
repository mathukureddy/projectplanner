from datetime import datetime


async def emit_integration_events(
    db,
    project_id: str,
    event_type: str,
    payload: dict | None = None,
    direction: str = "outbound",
    integration_type: str | None = None,
) -> int:
    """
    Best-effort event fanout to all enabled project integrations.
    We log events locally in `integration_events` and do not perform external calls.
    """
    try:
        project = await db["projects"].find_one({"_id": __import__("bson").ObjectId(project_id)})
    except Exception:
        return 0
    if not project:
        return 0

    configured = project.get("integrations") or []
    docs = []
    for cfg in configured:
        if not isinstance(cfg, dict):
            continue
        itype = str(cfg.get("type") or "").strip().lower()
        if itype not in ("webhook", "slack", "email"):
            continue
        if integration_type and itype != integration_type:
            continue
        if not bool(cfg.get("enabled", True)):
            continue
        docs.append(
            {
                "project_id": project_id,
                "integration_type": itype,
                "event_type": event_type,
                "direction": direction,
                "payload": payload or {},
                "endpoint": cfg.get("endpoint"),
                "created_at": datetime.utcnow(),
            }
        )
    if docs:
        await db["integration_events"].insert_many(docs)
    return len(docs)

