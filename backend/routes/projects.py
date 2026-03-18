from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException
from bson import ObjectId
from pymongo.errors import PyMongoError

from db import get_database, normalize_document, apply_status_completion_rules
from models import Project, ProjectCreateWithTasks, ProjectUpdate


router = APIRouter()


def _serialize_project(doc: dict) -> Project:
    # Mongo stores document id in `_id`. Expose it as `id` for the frontend.
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
    result = await db["projects"].find_one_and_update(
        {"_id": oid},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return _serialize_project(result)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str) -> None:
    db = get_database()
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")
    await db["projects"].delete_one({"_id": oid})
    return None

