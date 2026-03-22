from datetime import datetime
from typing import List

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_database
from models import IntegrationConfig, IntegrationEvent


router = APIRouter()


class IntegrationPatchPayload(BaseModel):
    integrations: List[IntegrationConfig] = Field(default_factory=list)


class IntegrationTestPayload(BaseModel):
    integration_type: str
    event_type: str = "manual_test"
    payload: dict = Field(default_factory=dict)


def _serialize_event(doc: dict) -> IntegrationEvent:
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return IntegrationEvent(**doc)


async def _project_or_404(project_id: str) -> dict:
    db = get_database()
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")
    doc = await db["projects"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    return doc


@router.get("/{project_id}/integrations", response_model=List[IntegrationConfig])
async def list_integrations(project_id: str) -> List[IntegrationConfig]:
    project = await _project_or_404(project_id)
    raw = project.get("integrations") or []
    out = []
    for item in raw:
        try:
            out.append(IntegrationConfig(**item))
        except Exception:
            continue
    return out


@router.patch("/{project_id}/integrations", response_model=List[IntegrationConfig])
async def patch_integrations(project_id: str, payload: IntegrationPatchPayload) -> List[IntegrationConfig]:
    await _project_or_404(project_id)
    db = get_database()
    docs = [x.model_dump() for x in payload.integrations]
    await db["projects"].update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"integrations": docs, "updated_at": datetime.utcnow()}},
    )
    return payload.integrations


@router.post("/{project_id}/integrations/test", response_model=dict)
async def test_integration(project_id: str, payload: IntegrationTestPayload) -> dict:
    project = await _project_or_404(project_id)
    db = get_database()

    integration_type = payload.integration_type.strip().lower()
    enabled = False
    endpoint = None
    for cfg in project.get("integrations") or []:
        if cfg.get("type") == integration_type:
            enabled = bool(cfg.get("enabled", True))
            endpoint = cfg.get("endpoint")
            break
    if not enabled:
        raise HTTPException(status_code=400, detail=f"{integration_type} integration is disabled or not configured")

    # We intentionally log instead of making external network calls (safe local dev).
    await db["integration_events"].insert_one(
        {
            "project_id": project_id,
            "integration_type": integration_type,
            "event_type": payload.event_type,
            "direction": "outbound",
            "payload": payload.payload,
            "endpoint": endpoint,
            "created_at": datetime.utcnow(),
        }
    )
    return {"status": "ok", "message": "Integration test event logged"}


@router.post("/{project_id}/integrations/webhook/{integration_type}", response_model=dict)
async def inbound_webhook(project_id: str, integration_type: str, payload: dict) -> dict:
    await _project_or_404(project_id)
    db = get_database()
    await db["integration_events"].insert_one(
        {
            "project_id": project_id,
            "integration_type": integration_type.lower(),
            "event_type": "webhook_received",
            "direction": "inbound",
            "payload": payload or {},
            "created_at": datetime.utcnow(),
        }
    )
    return {"status": "ok"}


@router.get("/{project_id}/integrations/events", response_model=List[IntegrationEvent])
async def integration_events(
    project_id: str,
    integration_type: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=1000),
) -> List[IntegrationEvent]:
    await _project_or_404(project_id)
    db = get_database()
    q = {"project_id": project_id}
    if integration_type:
        q["integration_type"] = integration_type.lower()
    out = []
    async for doc in db["integration_events"].find(q).sort("created_at", -1).limit(limit):
        out.append(_serialize_event(doc))
    return out

