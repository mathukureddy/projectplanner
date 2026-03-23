from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from pymongo.errors import PyMongoError

from db import get_database
from models import Comment, CommentCreate
from notification_logic import create_user_notification, extract_mentions

router = APIRouter()


def _serialize_comment(doc: dict) -> Comment:
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return Comment(**doc)


async def _task_belongs_to_project(db, task_id: str, project_id: str) -> bool:
    try:
        oid = ObjectId(task_id)
    except Exception:
        return False
    doc = await db["tasks"].find_one({"_id": oid, "project_id": project_id})
    return doc is not None


@router.get("/", response_model=list[Comment])
async def list_comments(
    task_id: str = Query(..., description="Task id"),
    project_id: str = Query(..., description="Project id (for validation)"),
) -> list[Comment]:
    db = get_database()
    if not await _task_belongs_to_project(db, task_id, project_id):
        raise HTTPException(status_code=404, detail="Task not found in this project")
    out: list[Comment] = []
    async for doc in db["comments"].find({"task_id": task_id}).sort("created_at", 1):
        out.append(_serialize_comment(doc))
    return out


@router.post("/", response_model=Comment, status_code=201)
async def create_comment(payload: CommentCreate, project_id: str = Query(...)) -> Comment:
    db = get_database()
    if not await _task_belongs_to_project(db, payload.task_id, project_id):
        raise HTTPException(status_code=404, detail="Task not found in this project")
    now = datetime.utcnow()
    doc = {
        "project_id": project_id,
        "task_id": payload.task_id,
        "author": payload.author.strip(),
        "body": payload.body,
        "created_at": now,
    }
    try:
        result = await db["comments"].insert_one(doc)
        created = await db["comments"].find_one({"_id": result.inserted_id})
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e.__class__.__name__}")

    # Collaboration notifications: @mentions in comments create recipient-targeted alerts.
    try:
        mentions = [u for u in extract_mentions(payload.body) if u.lower() != payload.author.strip().lower()]
        for username in mentions:
            await create_user_notification(
                db,
                project_id=project_id,
                task_id=payload.task_id,
                recipient_user=username,
                title=f"Mentioned by {payload.author}",
                message=f'You were mentioned in a comment: "{payload.body}"',
                kind="comment_mention",
                dedupe_key={"task_id": payload.task_id, "message": f'You were mentioned in a comment: "{payload.body}"'},
            )
    except Exception:
        pass
    return _serialize_comment(created)


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(comment_id: str, project_id: str = Query(...)) -> None:
    db = get_database()
    try:
        oid = ObjectId(comment_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid comment id")
    res = await db["comments"].delete_one({"_id": oid, "project_id": project_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Comment not found")
    return None
