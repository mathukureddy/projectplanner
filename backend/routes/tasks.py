from datetime import datetime
from typing import Dict, List

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


def _to_oid(task_id: str) -> ObjectId:
    try:
        return ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task id")


async def _validate_parent_task(db, project_id: str, parent_task_id: str, task_id: str | None = None) -> None:
    if not parent_task_id:
        return
    try:
        parent_oid = ObjectId(parent_task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid parent_task_id")
    if task_id and parent_task_id == task_id:
        raise HTTPException(status_code=400, detail="Task cannot be its own parent")
    parent = await db["tasks"].find_one({"_id": parent_oid, "project_id": project_id})
    if not parent:
        raise HTTPException(status_code=400, detail="parent_task_id must reference a task in the same project")

    # Prevent direct two-node cycles.
    if task_id and parent.get("parent_task_id") == task_id:
        raise HTTPException(status_code=400, detail="Invalid hierarchy cycle detected")


def _task_duration_days(doc: dict) -> int:
    explicit = doc.get("duration_days")
    if explicit is not None:
        return max(1, int(explicit))
    start = doc.get("start_date")
    end = doc.get("end_date")
    if start and end:
        try:
            return max(1, (end.date() - start.date()).days + 1)
        except Exception:
            return 1
    return 1


def _detect_dependency_cycle(task_docs: List[dict]) -> bool:
    ids = {str(doc["_id"]) for doc in task_docs}
    adjacency: Dict[str, List[str]] = {task_id: [] for task_id in ids}
    for doc in task_docs:
        task_id = str(doc["_id"])
        for pred in doc.get("predecessors", []) or []:
            if pred in ids:
                adjacency[pred].append(task_id)

    visiting = set()
    visited = set()

    def dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in adjacency.get(node, []):
            if dfs(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(dfs(n) for n in ids if n not in visited)


async def _validate_predecessors(
    db,
    project_id: str,
    predecessors: List[str] | None,
    task_id: str | None = None,
) -> None:
    if predecessors is None:
        return
    predecessor_ids = predecessors or []
    if task_id and task_id in predecessor_ids:
        raise HTTPException(status_code=400, detail="Task cannot depend on itself")

    for pred in predecessor_ids:
        try:
            pred_oid = ObjectId(pred)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid predecessor id")
        pred_task = await db["tasks"].find_one({"_id": pred_oid, "project_id": project_id})
        if not pred_task:
            raise HTTPException(status_code=400, detail="Each predecessor must reference a task in the same project")

    current_docs = []
    async for doc in db["tasks"].find({"project_id": project_id}):
        current_docs.append(doc)
    if task_id:
        for doc in current_docs:
            if str(doc["_id"]) == task_id:
                doc["predecessors"] = predecessor_ids
                break
    else:
        # For create path, cycle check uses existing tasks only; new task cannot create
        # a cycle unless it references itself, which is already blocked above.
        return
    if _detect_dependency_cycle(current_docs):
        raise HTTPException(status_code=400, detail="Dependency cycle detected")


def _apply_critical_path_metrics(task_docs: List[dict]) -> List[dict]:
    by_id: Dict[str, dict] = {str(doc["_id"]): doc for doc in task_docs}
    ids = list(by_id.keys())
    preds: Dict[str, List[str]] = {tid: [] for tid in ids}
    succs: Dict[str, List[str]] = {tid: [] for tid in ids}
    in_degree: Dict[str, int] = {tid: 0 for tid in ids}

    for tid, doc in by_id.items():
        for pred in (doc.get("predecessors") or []):
            if pred in by_id:
                preds[tid].append(pred)
                succs[pred].append(tid)
                in_degree[tid] += 1

    queue = [tid for tid in ids if in_degree[tid] == 0]
    topo: List[str] = []
    while queue:
        node = queue.pop(0)
        topo.append(node)
        for s in succs[node]:
            in_degree[s] -= 1
            if in_degree[s] == 0:
                queue.append(s)
    if len(topo) != len(ids):
        return task_docs

    dur = {tid: _task_duration_days(by_id[tid]) for tid in ids}
    es: Dict[str, int] = {}
    ef: Dict[str, int] = {}
    for tid in topo:
        es[tid] = max((ef[p] for p in preds[tid]), default=0)
        ef[tid] = es[tid] + dur[tid]

    project_duration = max(ef.values(), default=0)
    ls: Dict[str, int] = {}
    lf: Dict[str, int] = {}
    for tid in reversed(topo):
        if not succs[tid]:
            lf[tid] = project_duration
        else:
            lf[tid] = min(ls[s] for s in succs[tid])
        ls[tid] = lf[tid] - dur[tid]

    for tid, doc in by_id.items():
        doc["earliest_start_day"] = es.get(tid, 0)
        doc["earliest_finish_day"] = ef.get(tid, dur[tid])
        doc["latest_start_day"] = ls.get(tid, 0)
        doc["latest_finish_day"] = lf.get(tid, dur[tid])
        doc["slack_days"] = max(0, doc["latest_start_day"] - doc["earliest_start_day"])
        doc["is_critical"] = doc["slack_days"] == 0
        baseline_start = doc.get("baseline_start")
        baseline_end = doc.get("baseline_end")
        if baseline_start and baseline_end and doc.get("start_date") and doc.get("end_date"):
            actual_duration = _task_duration_days(doc)
            baseline_duration = max(1, (baseline_end.date() - baseline_start.date()).days + 1)
            doc["baseline_variance_days"] = actual_duration - baseline_duration
        else:
            doc["baseline_variance_days"] = None
    return task_docs


def _apply_hierarchy_rollups(task_docs: List[dict]) -> List[dict]:
    by_id: Dict[str, dict] = {}
    children: Dict[str, List[str]] = {}
    for doc in task_docs:
        task_id = str(doc["_id"])
        by_id[task_id] = doc
        children.setdefault(task_id, [])
    for doc in task_docs:
        parent = doc.get("parent_task_id")
        child_id = str(doc["_id"])
        if parent and parent in by_id:
            children[parent].append(child_id)

    level_cache: Dict[str, int] = {}

    def get_level(task_id: str, seen: set[str] | None = None) -> int:
        if task_id in level_cache:
            return level_cache[task_id]
        seen = seen or set()
        if task_id in seen:
            return 0
        seen.add(task_id)
        parent_id = by_id[task_id].get("parent_task_id")
        if not parent_id or parent_id not in by_id:
            level_cache[task_id] = 0
            return 0
        level = get_level(parent_id, seen) + 1
        level_cache[task_id] = level
        return level

    rollup_cache: Dict[str, tuple[int, str]] = {}

    def compute_rollup(task_id: str) -> tuple[int, str]:
        if task_id in rollup_cache:
            return rollup_cache[task_id]
        child_ids = children.get(task_id, [])
        if not child_ids:
            pct = int(by_id[task_id].get("percent_complete", 0) or 0)
            status = by_id[task_id].get("status", "Not Started")
            rollup_cache[task_id] = (pct, status)
            return pct, status
        child_rollups = [compute_rollup(cid) for cid in child_ids]
        avg_pct = round(sum(p for p, _ in child_rollups) / len(child_rollups))
        statuses = [s for _, s in child_rollups]
        if all(s == "Complete" for s in statuses):
            status = "Complete"
        elif any(s == "In Progress" for s in statuses):
            status = "In Progress"
        elif any(s == "Blocked" for s in statuses):
            status = "Blocked"
        elif all(s == "Not Started" for s in statuses):
            status = "Not Started"
        else:
            status = "In Progress"
        rollup_cache[task_id] = (avg_pct, status)
        return avg_pct, status

    for task_id, doc in by_id.items():
        child_count = len(children.get(task_id, []))
        rollup_pct, rollup_status = compute_rollup(task_id)
        doc["hierarchy_level"] = get_level(task_id)
        doc["child_count"] = child_count
        doc["rollup_percent_complete"] = rollup_pct
        doc["rollup_status"] = rollup_status

    return task_docs


@router.get("/", response_model=List[Task])
async def list_tasks(project_id: str = Query(..., description="Filter by project id")) -> List[Task]:
    db = get_database()
    task_docs = []
    async for doc in db["tasks"].find({"project_id": project_id}):
        task_docs.append(doc)
    task_docs = _apply_hierarchy_rollups(task_docs)
    task_docs = _apply_critical_path_metrics(task_docs)
    return [_serialize_task(doc) for doc in task_docs]


@router.post("/", response_model=Task, status_code=201)
async def create_task(payload: TaskCreate) -> Task:
    db = get_database()
    now = datetime.utcnow()
    doc = apply_status_completion_rules(normalize_document(payload.model_dump()))
    await _validate_parent_task(db, payload.project_id, doc.get("parent_task_id"))
    await _validate_predecessors(db, payload.project_id, doc.get("predecessors"))
    doc.update({"created_at": now, "updated_at": now})
    try:
        result = await db["tasks"].insert_one(doc)
        created = await db["tasks"].find_one({"_id": result.inserted_id})
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e.__class__.__name__}")
    project_docs = []
    async for tdoc in db["tasks"].find({"project_id": payload.project_id}):
        project_docs.append(tdoc)
    project_docs = _apply_hierarchy_rollups(project_docs)
    project_docs = _apply_critical_path_metrics(project_docs)
    mapped = {str(t["_id"]): t for t in project_docs}
    return _serialize_task(mapped[str(created["_id"])])


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str) -> Task:
    db = get_database()
    oid = _to_oid(task_id)
    doc = await db["tasks"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found")
    project_docs = []
    async for tdoc in db["tasks"].find({"project_id": doc["project_id"]}):
        project_docs.append(tdoc)
    project_docs = _apply_hierarchy_rollups(project_docs)
    project_docs = _apply_critical_path_metrics(project_docs)
    mapped = {str(t["_id"]): t for t in project_docs}
    return _serialize_task(mapped[task_id])


@router.patch("/{task_id}", response_model=Task)
async def update_task(task_id: str, payload: TaskUpdate) -> Task:
    db = get_database()
    oid = _to_oid(task_id)
    current = await db["tasks"].find_one({"_id": oid})
    if not current:
        raise HTTPException(status_code=404, detail="Task not found")
    updates = apply_status_completion_rules(
        normalize_document({k: v for k, v in payload.model_dump(exclude_unset=True).items()})
    )
    if "parent_task_id" in updates:
        await _validate_parent_task(
            db,
            current["project_id"],
            updates.get("parent_task_id"),
            task_id=task_id,
        )
    if "predecessors" in updates:
        await _validate_predecessors(
            db,
            current["project_id"],
            updates.get("predecessors"),
            task_id=task_id,
        )
    if not updates:
        project_docs = []
        async for tdoc in db["tasks"].find({"project_id": current["project_id"]}):
            project_docs.append(tdoc)
        project_docs = _apply_hierarchy_rollups(project_docs)
        project_docs = _apply_critical_path_metrics(project_docs)
        mapped = {str(t["_id"]): t for t in project_docs}
        return _serialize_task(mapped[task_id])
    updates["updated_at"] = datetime.utcnow()
    result = await db["tasks"].find_one_and_update(
        {"_id": oid},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    project_docs = []
    async for tdoc in db["tasks"].find({"project_id": current["project_id"]}):
        project_docs.append(tdoc)
    project_docs = _apply_hierarchy_rollups(project_docs)
    project_docs = _apply_critical_path_metrics(project_docs)
    mapped = {str(t["_id"]): t for t in project_docs}
    return _serialize_task(mapped[task_id])


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str) -> None:
    db = get_database()
    oid = _to_oid(task_id)
    task = await db["tasks"].find_one({"_id": oid})
    if not task:
        return None
    # Promote children to this task's parent to preserve hierarchy continuity.
    await db["tasks"].update_many(
        {"project_id": task["project_id"], "parent_task_id": task_id},
        {"$set": {"parent_task_id": task.get("parent_task_id")}},
    )
    await db["tasks"].delete_one({"_id": oid})
    return None

