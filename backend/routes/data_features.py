from __future__ import annotations

import ast
from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from db import get_database
from models import CellHistoryEntry, FormulaRule, GovernancePolicy


router = APIRouter()


def _safe_eval_formula(expr: str, context: dict[str, Any]) -> Any:
    """
    Very small arithmetic evaluator for formulas.
    Allowed: +, -, *, /, parentheses, names from context.
    """
    node = ast.parse(expr, mode="eval")
    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Load,
        ast.Constant,
        ast.Name,
    )
    for n in ast.walk(node):
        if not isinstance(n, allowed_nodes):
            raise ValueError("Unsupported formula syntax")
        if isinstance(n, ast.Name) and n.id not in context:
            raise ValueError(f"Unknown field '{n.id}'")
    return eval(compile(node, "<formula>", "eval"), {"__builtins__": {}}, context)


async def _project_or_404(db, project_id: str) -> dict:
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project id")
    doc = await db["projects"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    return doc


def _normalize_rule(rule: dict) -> Optional[dict]:
    try:
        r = FormulaRule(**rule)
        return r.model_dump()
    except Exception:
        return None


@router.get("/{project_id}/formulas", response_model=list[FormulaRule])
async def list_formulas(project_id: str) -> list[FormulaRule]:
    db = get_database()
    project = await _project_or_404(db, project_id)
    formulas = project.get("formulas") or []
    out = []
    for f in formulas:
        n = _normalize_rule(f)
        if n:
            out.append(FormulaRule(**n))
    return out


@router.patch("/{project_id}/formulas", response_model=list[FormulaRule])
async def patch_formulas(project_id: str, payload: list[FormulaRule]) -> list[FormulaRule]:
    db = get_database()
    await _project_or_404(db, project_id)
    docs = [p.model_dump() for p in payload]
    await db["projects"].update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"formulas": docs, "updated_at": datetime.utcnow()}},
    )
    return payload


@router.post("/{project_id}/formulas/evaluate", response_model=dict)
async def evaluate_formulas(project_id: str) -> dict:
    """
    Evaluate all enabled formulas for each task in this project.

    Supported expression forms:
    - Arithmetic with task field names, e.g. `percent_complete * 0.5`
    - Cross-sheet reference (single value):
      `XREF(project_id,task_name,field_name)`
    """
    db = get_database()
    project = await _project_or_404(db, project_id)
    formulas = [f for f in (project.get("formulas") or []) if bool(f.get("enabled", True))]
    if not formulas:
        return {"status": "ok", "updated_tasks": 0, "applied": 0}

    updated_tasks = 0
    applied = 0

    async for task in db["tasks"].find({"project_id": project_id}):
        updates: dict[str, Any] = {}
        task_id = str(task["_id"])
        context = {}
        for k, v in task.items():
            if k.startswith("_"):
                continue
            if isinstance(v, (int, float)):
                context[k] = v
            elif isinstance(v, str):
                try:
                    context[k] = float(v)
                except Exception:
                    pass

        for f in formulas:
            expr = str(f.get("expression") or "").strip()
            target = str(f.get("target_field") or "").strip()
            if not expr or not target:
                continue
            value = None
            try:
                if expr.startswith("XREF(") and expr.endswith(")"):
                    # XREF(project_id,task_name,field_name)
                    inner = expr[5:-1]
                    parts = [x.strip() for x in inner.split(",")]
                    if len(parts) != 3:
                        continue
                    src_project_id, src_task_name, src_field = parts
                    src = await db["tasks"].find_one(
                        {"project_id": src_project_id, "name": src_task_name}
                    )
                    if src is not None:
                        value = src.get(src_field)
                else:
                    value = _safe_eval_formula(expr, context)
            except Exception:
                continue

            if value is not None and task.get(target) != value:
                updates[target] = value
                await db["cell_history"].insert_one(
                    {
                        "project_id": project_id,
                        "task_id": task_id,
                        "field": target,
                        "old_value": str(task.get(target)) if task.get(target) is not None else None,
                        "new_value": str(value),
                        "changed_by": "formula_engine",
                        "source": "formula",
                        "changed_at": datetime.utcnow(),
                    }
                )
                applied += 1

        if updates:
            updates["updated_at"] = datetime.utcnow()
            await db["tasks"].update_one({"_id": task["_id"]}, {"$set": updates})
            updated_tasks += 1

    return {"status": "ok", "updated_tasks": updated_tasks, "applied": applied}


@router.get("/{project_id}/cross-sheet/reference", response_model=dict)
async def cross_sheet_reference(
    project_id: str,
    source_project_id: str = Query(...),
    task_name: str = Query(...),
    field: str = Query(...),
) -> dict:
    db = get_database()
    await _project_or_404(db, project_id)
    doc = await db["tasks"].find_one({"project_id": source_project_id, "name": task_name})
    if not doc:
        raise HTTPException(status_code=404, detail="Source task not found")
    return {"value": doc.get(field)}


@router.get("/{project_id}/cell-history", response_model=list[CellHistoryEntry])
async def list_cell_history(
    project_id: str,
    task_id: Optional[str] = Query(None),
    field: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> list[CellHistoryEntry]:
    db = get_database()
    await _project_or_404(db, project_id)
    q: dict[str, Any] = {"project_id": project_id}
    if task_id:
        q["task_id"] = task_id
    if field:
        q["field"] = field

    out = []
    async for row in db["cell_history"].find(q).sort("changed_at", -1).limit(limit):
        row["id"] = str(row["_id"])
        row.pop("_id", None)
        out.append(CellHistoryEntry(**row))
    return out


@router.get("/{project_id}/governance", response_model=GovernancePolicy)
async def get_governance(project_id: str) -> GovernancePolicy:
    db = get_database()
    project = await _project_or_404(db, project_id)
    gov = project.get("governance") or {}
    return GovernancePolicy(
        locked_fields=[str(x) for x in (gov.get("locked_fields") or [])],
        restrict_locked_to_admin=bool(gov.get("restrict_locked_to_admin", True)),
    )


@router.patch("/{project_id}/governance", response_model=GovernancePolicy)
async def patch_governance(project_id: str, payload: GovernancePolicy) -> GovernancePolicy:
    db = get_database()
    await _project_or_404(db, project_id)
    doc = payload.model_dump()
    await db["projects"].update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"governance": doc, "updated_at": datetime.utcnow()}},
    )
    return payload

