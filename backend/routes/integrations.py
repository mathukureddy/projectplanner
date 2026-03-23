import base64
import json
from datetime import date, datetime
from typing import List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_database
from models import IntegrationConfig, IntegrationEvent, TaskCreate
from routes.tasks import create_task_document


router = APIRouter()


class IntegrationPatchPayload(BaseModel):
    integrations: List[IntegrationConfig] = Field(default_factory=list)


class IntegrationTestPayload(BaseModel):
    integration_type: str
    event_type: str = "manual_test"
    payload: dict = Field(default_factory=dict)


class JiraImportPayload(BaseModel):
    jql: str = ""
    max_results: int = Field(default=20, ge=1, le=200)


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


def _get_integration(project: dict, integration_type: str) -> dict | None:
    target = integration_type.strip().lower()
    for cfg in project.get("integrations") or []:
        if isinstance(cfg, dict) and str(cfg.get("type", "")).lower() == target:
            return cfg
    return None


def _jira_auth_headers(cfg: dict) -> dict:
    settings = cfg.get("settings") or {}
    email = str(settings.get("jira_email") or "").strip()
    token = str(cfg.get("secret") or "").strip()
    if not email or not token:
        raise HTTPException(status_code=400, detail="Jira config requires jira_email (settings) and secret (API token)")
    basic = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {basic}",
        "Accept": "application/json",
    }


def _jira_base_url(cfg: dict) -> str:
    base = str(cfg.get("endpoint") or "").strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=400, detail="Jira endpoint is required")
    return base


def _parse_issue_date(v) -> date | None:
    if not v:
        return None
    s = str(v)
    if len(s) >= 10:
        s = s[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _jira_issue_to_task(project_id: str, issue: dict) -> TaskCreate:
    fields = issue.get("fields") or {}
    summary = str(fields.get("summary") or issue.get("key") or "Jira issue").strip()[:500]
    desc_val = fields.get("description")
    if isinstance(desc_val, dict):
        description = json.dumps(desc_val)[:8000]
    else:
        description = (str(desc_val).strip() if desc_val else None)
    assignee = (fields.get("assignee") or {}).get("displayName") or (fields.get("assignee") or {}).get("emailAddress")
    status_name = str((fields.get("status") or {}).get("name") or "").strip().lower()
    mapped_status = "Not Started"
    if status_name in ("done", "complete", "completed", "closed", "resolved"):
        mapped_status = "Complete"
    elif status_name in ("in progress", "doing"):
        mapped_status = "In Progress"
    elif status_name in ("blocked",):
        mapped_status = "Blocked"
    due = _parse_issue_date(fields.get("duedate"))
    start = _parse_issue_date(fields.get("created"))
    return TaskCreate(
        project_id=project_id,
        name=summary,
        description=description,
        assigned_to=str(assignee).strip() if assignee else None,
        status=mapped_status,
        start_date=start,
        end_date=due,
    )


def _fetch_jira_issues(cfg: dict, payload: JiraImportPayload) -> list[dict]:
    settings = cfg.get("settings") or {}
    mock_issues = settings.get("mock_issues")
    if isinstance(mock_issues, list):
        return mock_issues[: payload.max_results]

    base = _jira_base_url(cfg)
    jql = payload.jql.strip() or str(settings.get("jira_jql") or "").strip() or "ORDER BY updated DESC"
    max_results = int(payload.max_results)
    body = json.dumps(
        {
            "jql": jql,
            "maxResults": max_results,
            "fields": ["summary", "description", "assignee", "status", "duedate", "created"],
        }
    ).encode("utf-8")
    headers = _jira_auth_headers(cfg)
    headers["Content-Type"] = "application/json"
    req = Request(url=f"{base}/rest/api/3/search", data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("issues") or []
    except HTTPError as e:
        detail = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
        raise HTTPException(status_code=400, detail=f"Jira request failed: {detail[:500]}")
    except URLError as e:
        raise HTTPException(status_code=400, detail=f"Jira connection failed: {e.reason}")


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
    cfg = _get_integration(project, integration_type)
    enabled = bool((cfg or {}).get("enabled", True)) if cfg else False
    endpoint = (cfg or {}).get("endpoint")
    if not enabled:
        raise HTTPException(status_code=400, detail=f"{integration_type} integration is disabled or not configured")

    if integration_type == "jira":
        # Real validation: Jira "myself" endpoint.
        settings = cfg.get("settings") or {}
        if isinstance(settings.get("mock_issues"), list):
            pass
        else:
            base = _jira_base_url(cfg)
            headers = _jira_auth_headers(cfg)
            req = Request(url=f"{base}/rest/api/3/myself", headers=headers, method="GET")
            try:
                with urlopen(req, timeout=15) as resp:
                    if resp.status >= 400:
                        raise HTTPException(status_code=400, detail="Jira authentication failed")
            except HTTPError as e:
                detail = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
                raise HTTPException(status_code=400, detail=f"Jira test failed: {detail[:500]}")
            except URLError as e:
                raise HTTPException(status_code=400, detail=f"Jira connection failed: {e.reason}")

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


@router.post("/{project_id}/integrations/jira/import", response_model=dict)
async def import_jira_issues(project_id: str, payload: JiraImportPayload) -> dict:
    project = await _project_or_404(project_id)
    db = get_database()
    cfg = _get_integration(project, "jira")
    if not cfg or not bool(cfg.get("enabled", True)):
        raise HTTPException(status_code=400, detail="jira integration is disabled or not configured")

    issues = _fetch_jira_issues(cfg, payload)
    created = 0
    skipped = 0
    imported_keys: list[str] = []
    for issue in issues:
        issue_key = str(issue.get("key") or "").strip()
        if not issue_key:
            skipped += 1
            continue
        marker = f"[JIRA:{issue_key}]"
        exists = await db["tasks"].find_one({"project_id": project_id, "jira_issue_key": issue_key})
        if exists:
            skipped += 1
            continue

        task_payload = _jira_issue_to_task(project_id, issue)
        if task_payload.description:
            task_payload.description = f"{task_payload.description}\n\n{marker}"
        else:
            task_payload.description = marker
        created_task = await create_task_document(db, task_payload)
        await db["tasks"].update_one(
            {"_id": ObjectId(created_task.id)},
            {"$set": {"jira_issue_key": issue_key, "updated_at": datetime.utcnow()}},
        )
        imported_keys.append(issue_key)
        created += 1

    await db["integration_events"].insert_one(
        {
            "project_id": project_id,
            "integration_type": "jira",
            "event_type": "jira_import",
            "direction": "inbound",
            "payload": {"created": created, "skipped": skipped, "issues": imported_keys},
            "created_at": datetime.utcnow(),
        }
    )
    return {"status": "ok", "created": created, "skipped": skipped, "issues": imported_keys}


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

