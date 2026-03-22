import os
import re
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pymongo.errors import PyMongoError

from db import get_database
from models import AttachmentOut
from storage import UPLOAD_ROOT

router = APIRouter()


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "upload")
    base = re.sub(r"[^a-zA-Z0-9._-]+", "_", base).strip("._") or "file"
    return base[:180]


def _serialize_attachment(doc: dict) -> AttachmentOut:
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return AttachmentOut(**doc)


async def _task_belongs_to_project(db, task_id: str, project_id: str) -> bool:
    try:
        oid = ObjectId(task_id)
    except Exception:
        return False
    doc = await db["tasks"].find_one({"_id": oid, "project_id": project_id})
    return doc is not None


@router.get("/", response_model=list[AttachmentOut])
async def list_attachments(
    task_id: str = Query(...),
    project_id: str = Query(...),
) -> list[AttachmentOut]:
    db = get_database()
    if not await _task_belongs_to_project(db, task_id, project_id):
        raise HTTPException(status_code=404, detail="Task not found in this project")
    out: list[AttachmentOut] = []
    async for doc in db["attachments"].find({"task_id": task_id}).sort("created_at", -1):
        out.append(_serialize_attachment(doc))
    return out


@router.post("/upload", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    project_id: str = Form(...),
    task_id: str = Form(...),
    uploaded_by: str = Form(""),
    file: UploadFile = File(...),
) -> AttachmentOut:
    db = get_database()
    if not await _task_belongs_to_project(db, task_id, project_id):
        raise HTTPException(status_code=404, detail="Task not found in this project")

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    oid = ObjectId()
    safe = _safe_filename(file.filename or "file")
    rel_dir = str(oid)
    dest_dir = UPLOAD_ROOT / rel_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe

    try:
        content = await file.read()
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large (max 25MB)")
        dest_path.write_bytes(content)
    except HTTPException:
        raise
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    now = datetime.utcnow()
    doc = {
        "_id": oid,
        "project_id": project_id,
        "task_id": task_id,
        "filename": file.filename or safe,
        "content_type": file.content_type or "application/octet-stream",
        "size": len(content),
        "disk_relative": f"{rel_dir}/{safe}",
        "uploaded_by": uploaded_by.strip() or None,
        "created_at": now,
    }
    try:
        await db["attachments"].insert_one(doc)
    except PyMongoError as e:
        try:
            dest_path.unlink(missing_ok=True)
            dest_dir.rmdir()
        except OSError:
            pass
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e.__class__.__name__}")

    return _serialize_attachment(await db["attachments"].find_one({"_id": oid}))


@router.get("/{attachment_id}/file")
async def download_file(attachment_id: str, project_id: str) -> FileResponse:
    db = get_database()
    try:
        oid = ObjectId(attachment_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid attachment id")
    doc = await db["attachments"].find_one({"_id": oid, "project_id": project_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = UPLOAD_ROOT / doc["disk_relative"]
    if not path.is_file() or not str(path.resolve()).startswith(str(UPLOAD_ROOT.resolve())):
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(
        path,
        filename=doc["filename"],
        media_type=doc.get("content_type") or "application/octet-stream",
    )


@router.delete("/{attachment_id}", status_code=204)
async def delete_attachment(
    attachment_id: str,
    project_id: str = Query(...),
) -> None:
    db = get_database()
    try:
        oid = ObjectId(attachment_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid attachment id")
    doc = await db["attachments"].find_one({"_id": oid, "project_id": project_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = UPLOAD_ROOT / doc["disk_relative"]
    await db["attachments"].delete_one({"_id": oid})
    try:
        if path.is_file():
            path.unlink()
        parent = path.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass
    return None
