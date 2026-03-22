"""
Intake forms: configurable per-project forms whose submissions create tasks (new rows).
Public submit by unguessable slug — no auth required.
"""

import re
import secrets
from datetime import date, datetime
from typing import Any, Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pymongo.errors import PyMongoError

from db import get_database
from models import (
    IntakeFormCreate,
    IntakeFormOut,
    IntakeFormPublicOut,
    IntakeFormUpdate,
    IntakeFormField,
    IntakeSubmitPayload,
    IntakeSubmissionOut,
    TaskCreate,
)
from routes.tasks import create_task_document

router = APIRouter()
public_router = APIRouter(tags=["intake-forms-public"])


def _slug() -> str:
    return secrets.token_urlsafe(18).replace("-", "_")[:32]


async def _project_exists(db, project_id: str) -> bool:
    try:
        oid = ObjectId(project_id)
    except Exception:
        return False
    return await db["projects"].find_one({"_id": oid}) is not None


def _form_doc_to_out(doc: dict) -> IntakeFormOut:
    d = dict(doc)
    d["id"] = str(d.pop("_id"))
    fields = [IntakeFormField(**f) if isinstance(f, dict) else f for f in d.get("fields", [])]
    return IntakeFormOut(
        id=d["id"],
        project_id=d["project_id"],
        slug=d["slug"],
        name=d["name"],
        enabled=bool(d.get("enabled", True)),
        fields=fields,
        task_name_field=d["task_name_field"],
        task_description_field=d.get("task_description_field"),
        task_assigned_to_field=d.get("task_assigned_to_field"),
        task_start_date_field=d.get("task_start_date_field"),
        task_end_date_field=d.get("task_end_date_field"),
        default_status=d.get("default_status") or "Not Started",
        created_at=d["created_at"],
        updated_at=d.get("updated_at") or d["created_at"],
    )


def _basic_email(s: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", (s or "").strip()))


def _parse_date_val(raw: Any) -> Optional[date]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date (use YYYY-MM-DD): {s!r}")


def _validate_and_normalize_responses(fields: list[dict], responses: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    keys_in_form = {f["key"] for f in fields}
    for f in fields:
        key = f["key"]
        raw = responses.get(key)
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            if f.get("required"):
                raise HTTPException(status_code=400, detail=f"Missing required field: {f.get('label', key)}")
            out[key] = None
            continue
        t = f.get("type") or "text"
        if t == "number":
            try:
                v = float(raw)
                out[key] = int(v) if v == int(v) else v
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"Field {key!r} must be a number")
        elif t == "email":
            s = str(raw).strip()
            if not _basic_email(s):
                raise HTTPException(status_code=400, detail=f"Field {key!r} must be a valid email")
            out[key] = s
        elif t == "date":
            out[key] = _parse_date_val(raw)
        else:
            out[key] = str(raw).strip()
    for k in responses:
        if k not in keys_in_form:
            raise HTTPException(status_code=400, detail=f"Unknown field: {k}")
    return out


def _build_task_payload(form: dict, norm: dict[str, Any]) -> TaskCreate:
    name_key = form["task_name_field"]
    name_val = norm.get(name_key)
    if not name_val:
        raise HTTPException(status_code=400, detail="Task name field cannot be empty")

    desc_parts: list[str] = []
    desc_key = form.get("task_description_field")
    if desc_key and norm.get(desc_key):
        desc_parts.append(str(norm[desc_key]))

    mapped = {
        name_key,
        desc_key,
        form.get("task_assigned_to_field"),
        form.get("task_start_date_field"),
        form.get("task_end_date_field"),
    }
    mapped.discard(None)
    for f in form.get("fields", []):
        k = f["key"]
        if k in mapped:
            continue
        v = norm.get(k)
        if v is None or v == "":
            continue
        label = f.get("label", k)
        desc_parts.append(f"{label}: {v}")

    description = "\n\n".join(desc_parts) if desc_parts else None
    if description and len(description) > 8000:
        description = description[:8000]

    assigned = None
    ak = form.get("task_assigned_to_field")
    if ak and norm.get(ak) is not None:
        assigned = str(norm[ak])

    start_d = None
    sk = form.get("task_start_date_field")
    if sk and norm.get(sk):
        v = norm[sk]
        start_d = v if isinstance(v, date) else None

    end_d = None
    ek = form.get("task_end_date_field")
    if ek and norm.get(ek):
        v = norm[ek]
        end_d = v if isinstance(v, date) else None

    status = form.get("default_status") or "Not Started"

    return TaskCreate(
        project_id=form["project_id"],
        name=str(name_val)[:500],
        description=description,
        assigned_to=assigned[:200] if assigned else None,
        start_date=start_d,
        end_date=end_d,
        status=status,
    )


@router.get("/{project_id}/intake-forms", response_model=list[IntakeFormOut])
async def list_intake_forms(project_id: str) -> list[IntakeFormOut]:
    db = get_database()
    if not await _project_exists(db, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    out: list[IntakeFormOut] = []
    async for doc in db["intake_forms"].find({"project_id": project_id}).sort("created_at", -1):
        out.append(_form_doc_to_out(doc))
    return out


@router.post("/{project_id}/intake-forms", response_model=IntakeFormOut, status_code=201)
async def create_intake_form(project_id: str, payload: IntakeFormCreate) -> IntakeFormOut:
    db = get_database()
    if not await _project_exists(db, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    now = datetime.utcnow()
    doc = {
        "project_id": project_id,
        "slug": _slug(),
        "name": payload.name.strip(),
        "enabled": payload.enabled,
        "fields": [f.model_dump() for f in payload.fields],
        "task_name_field": payload.task_name_field,
        "task_description_field": payload.task_description_field,
        "task_assigned_to_field": payload.task_assigned_to_field,
        "task_start_date_field": payload.task_start_date_field,
        "task_end_date_field": payload.task_end_date_field,
        "default_status": payload.default_status,
        "created_at": now,
        "updated_at": now,
    }
    try:
        res = await db["intake_forms"].insert_one(doc)
        created = await db["intake_forms"].find_one({"_id": res.inserted_id})
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e.__class__.__name__}")
    return _form_doc_to_out(created)


@router.get("/{project_id}/intake-forms/{form_id}", response_model=IntakeFormOut)
async def get_intake_form(project_id: str, form_id: str) -> IntakeFormOut:
    db = get_database()
    try:
        oid = ObjectId(form_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid form id")
    doc = await db["intake_forms"].find_one({"_id": oid, "project_id": project_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Form not found")
    return _form_doc_to_out(doc)


@router.patch("/{project_id}/intake-forms/{form_id}", response_model=IntakeFormOut)
async def patch_intake_form(project_id: str, form_id: str, payload: IntakeFormUpdate) -> IntakeFormOut:
    db = get_database()
    try:
        oid = ObjectId(form_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid form id")
    doc = await db["intake_forms"].find_one({"_id": oid, "project_id": project_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Form not found")

    data = payload.model_dump(exclude_unset=True)
    updates: dict[str, Any] = {}
    if "name" in data and data["name"] is not None:
        updates["name"] = str(data["name"]).strip()
    if "enabled" in data and data["enabled"] is not None:
        updates["enabled"] = bool(data["enabled"])
    if "fields" in data and data["fields"] is not None:
        updates["fields"] = data["fields"]
    if "default_status" in data and data["default_status"] is not None:
        updates["default_status"] = data["default_status"]
    for k in (
        "task_name_field",
        "task_description_field",
        "task_assigned_to_field",
        "task_start_date_field",
        "task_end_date_field",
    ):
        if k in data:
            updates[k] = data[k]

    if updates:
        # Re-validate mapping keys if fields or mappings changed
        merged = {**doc, **updates}
        if "fields" in updates or any(
            x in updates for x in ("task_name_field", "task_description_field", "task_assigned_to_field", "task_start_date_field", "task_end_date_field")
        ):
            try:
                raw_fields = merged["fields"]
                field_models = [
                    IntakeFormField(**f) if isinstance(f, dict) else f for f in raw_fields
                ]
                IntakeFormCreate(
                    name=merged.get("name", doc["name"]),
                    enabled=merged.get("enabled", doc.get("enabled", True)),
                    fields=field_models,
                    task_name_field=merged["task_name_field"],
                    task_description_field=merged.get("task_description_field"),
                    task_assigned_to_field=merged.get("task_assigned_to_field"),
                    task_start_date_field=merged.get("task_start_date_field"),
                    task_end_date_field=merged.get("task_end_date_field"),
                    default_status=merged.get("default_status") or "Not Started",
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        updates["updated_at"] = datetime.utcnow()
        await db["intake_forms"].update_one({"_id": oid}, {"$set": updates})
    refreshed = await db["intake_forms"].find_one({"_id": oid})
    return _form_doc_to_out(refreshed)


@router.delete("/{project_id}/intake-forms/{form_id}", status_code=204)
async def delete_intake_form(project_id: str, form_id: str) -> None:
    db = get_database()
    try:
        oid = ObjectId(form_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid form id")
    res = await db["intake_forms"].delete_one({"_id": oid, "project_id": project_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Form not found")
    await db["intake_submissions"].delete_many({"form_id": form_id, "project_id": project_id})
    return None


@router.get("/{project_id}/intake-forms/{form_id}/submissions", response_model=list[IntakeSubmissionOut])
async def list_submissions(project_id: str, form_id: str) -> list[IntakeSubmissionOut]:
    db = get_database()
    try:
        foid = ObjectId(form_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid form id")
    if not await db["intake_forms"].find_one({"_id": foid, "project_id": project_id}):
        raise HTTPException(status_code=404, detail="Form not found")
    out: list[IntakeSubmissionOut] = []
    async for sdoc in db["intake_submissions"].find({"project_id": project_id, "form_id": form_id}).sort(
        "submitted_at", -1
    ).limit(200):
        out.append(
            IntakeSubmissionOut(
                id=str(sdoc["_id"]),
                form_id=sdoc["form_id"],
                project_id=sdoc["project_id"],
                task_id=sdoc["task_id"],
                responses=sdoc.get("responses") or {},
                submitted_at=sdoc["submitted_at"],
            )
        )
    return out


@public_router.get("/public/{slug}", response_model=IntakeFormPublicOut)
async def public_form_schema(slug: str) -> IntakeFormPublicOut:
    db = get_database()
    doc = await db["intake_forms"].find_one({"slug": slug, "enabled": True})
    if not doc:
        raise HTTPException(status_code=404, detail="Form not found or disabled")
    try:
        poid = ObjectId(doc["project_id"])
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")
    proj = await db["projects"].find_one({"_id": poid})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    fields = [IntakeFormField(**f) for f in doc.get("fields", [])]
    return IntakeFormPublicOut(name=doc["name"], fields=fields, project_name=proj.get("name", "Project"))


@public_router.post("/public/{slug}/submit")
async def public_submit(slug: str, payload: IntakeSubmitPayload) -> dict:
    db = get_database()
    doc = await db["intake_forms"].find_one({"slug": slug, "enabled": True})
    if not doc:
        raise HTTPException(status_code=404, detail="Form not found or disabled")

    norm = _validate_and_normalize_responses(doc.get("fields", []), payload.responses or {})
    task_payload = _build_task_payload(doc, norm)

    task = await create_task_document(db, task_payload)
    now = datetime.utcnow()
    sub_doc = {
        "form_id": str(doc["_id"]),
        "project_id": doc["project_id"],
        "slug": slug,
        "responses": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in norm.items()},
        "task_id": task.id,
        "submitted_at": now,
    }
    try:
        ins = await db["intake_submissions"].insert_one(sub_doc)
        sub_id = str(ins.inserted_id)
    except PyMongoError:
        sub_id = ""

    return {
        "status": "ok",
        "message": "Your request was submitted. A new task was created in the project.",
        "task_id": task.id,
        "submission_id": sub_id,
    }
