from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from pymongo.errors import PyMongoError

from db import get_database, normalize_document, apply_status_completion_rules
from models import Task, TaskCreate, TaskUpdate


router = APIRouter()


def _serialize_task(doc: dict) -> Task:
    # Mongo stores document id in `_id`. Expose it as `id` for the frontend.
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return Task(**doc)


@router.get("/", response_model=List[Task])
async def list_tasks(project_id: str = Query(..., description="Filter by project id")) -> List[Task]:
    db = get_database()
    tasks = []
    async for doc in db["tasks"].find({"project_id": project_id}):
        tasks.append(_serialize_task(doc))
    return tasks


@router.post("/", response_model=Task, status_code=201)
async def create_task(payload: TaskCreate) -> Task:
    db = get_database()
    now = datetime.utcnow()
    doc = apply_status_completion_rules(normalize_document(payload.model_dump()))
    doc.update({"created_at": now, "updated_at": now})
    try:
        result = await db["tasks"].insert_one(doc)
        created = await db["tasks"].find_one({"_id": result.inserted_id})
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e.__class__.__name__}")
    return _serialize_task(created)


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str) -> Task:
    db = get_database()
    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task id")
    doc = await db["tasks"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found")
    return _serialize_task(doc)


@router.patch("/{task_id}", response_model=Task)
async def update_task(task_id: str, payload: TaskUpdate) -> Task:
    db = get_database()
    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task id")
    updates = apply_status_completion_rules(
        normalize_document({k: v for k, v in payload.model_dump(exclude_unset=True).items()})
    )
    if not updates:
        doc = await db["tasks"].find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Task not found")
        return _serialize_task(doc)
    updates["updated_at"] = datetime.utcnow()
    result = await db["tasks"].find_one_and_update(
        {"_id": oid},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return _serialize_task(result)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str) -> None:
    db = get_database()
    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task id")
    await db["tasks"].delete_one({"_id": oid})
    return None

