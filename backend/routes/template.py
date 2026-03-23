from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from db import apply_status_completion_rules, get_database, normalize_document


TEMPLATE_CATALOG = [
    {
        "id": "project-plan-basic",
        "name": "Project plan & schedule",
        "category": "project",
        "description": "Classic project plan with phases, dependencies, and milestones.",
        "project": {
            "status": "On Track",
            "tasks": [
                {"name": "Initiation", "status": "In Progress", "percent_complete": 30},
                {"name": "Planning", "status": "Not Started", "predecessors": []},
                {"name": "Execution", "status": "Not Started"},
                {"name": "Go-live milestone", "status": "Not Started"},
            ],
        },
    },
    {
        "id": "agile-sprint-board",
        "name": "Agile sprint board",
        "category": "agile",
        "description": "Sprint-ready task board for backlog to done flow.",
        "project": {
            "status": "On Track",
            "tasks": [
                {"name": "Backlog grooming", "status": "In Progress"},
                {"name": "Sprint planning", "status": "Not Started"},
                {"name": "Development", "status": "Not Started"},
                {"name": "QA / demo", "status": "Not Started"},
            ],
        },
    },
    {
        "id": "marketing-campaign",
        "name": "Marketing campaign",
        "category": "marketing",
        "description": "Campaign planning template for launch readiness.",
        "project": {
            "status": "On Track",
            "tasks": [
                {"name": "Creative brief", "status": "In Progress"},
                {"name": "Asset production", "status": "Not Started"},
                {"name": "Channel scheduling", "status": "Not Started"},
                {"name": "Performance review", "status": "Not Started"},
            ],
        },
    },
    {
        "id": "it-intake-board",
        "name": "IT work intake",
        "category": "it",
        "description": "Intake and triage board for IT requests.",
        "project": {
            "status": "On Track",
            "tasks": [
                {"name": "New request triage", "status": "In Progress"},
                {"name": "Prioritization", "status": "Not Started"},
                {"name": "Implementation", "status": "Not Started"},
                {"name": "Validation & close", "status": "Not Started"},
            ],
        },
    },
]

SOLUTION_SETS = [
    {
        "id": "pmo-starter",
        "name": "PMO starter set",
        "description": "Portfolio + delivery starter for PMO teams.",
        "template_ids": ["project-plan-basic", "agile-sprint-board"],
    },
    {
        "id": "marketing-ops-set",
        "name": "Marketing ops set",
        "description": "Campaign execution + intake workflow starter.",
        "template_ids": ["marketing-campaign", "it-intake-board"],
    },
]

router = APIRouter()


@router.get("/project-template", response_class=FileResponse)
async def get_project_template() -> FileResponse:
    base_dir = Path(__file__).resolve().parents[2]
    template_path = base_dir / "Project-Template.json"
    return FileResponse(template_path)


@router.get("/catalog")
async def template_catalog() -> list[dict]:
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "category": t["category"],
            "description": t["description"],
            "task_count": len(t["project"]["tasks"]),
        }
        for t in TEMPLATE_CATALOG
    ]


@router.get("/solution-sets")
async def template_solution_sets() -> list[dict]:
    return SOLUTION_SETS


async def _create_project_from_template(template: dict, name: str) -> dict:
    db = get_database()
    now = datetime.utcnow()
    if await db["projects"].find_one({"name": name}):
        raise HTTPException(status_code=409, detail=f"Project name already exists: {name}")
    payload = template["project"]
    p_doc = normalize_document(
        {
            "name": name,
            "description": template["description"],
            "status": payload.get("status", "On Track"),
            "shares": [],
            "formulas": [],
            "governance": {
                "locked_fields": [],
                "restrict_locked_to_admin": True,
                "required_fields": [],
                "allowed_statuses": [],
                "edit_window_days": None,
            },
            "integrations": [],
            "created_at": now,
            "updated_at": now,
        }
    )
    ins = await db["projects"].insert_one(p_doc)
    project_id = str(ins.inserted_id)
    task_docs = []
    for t in payload.get("tasks", []):
        task_docs.append(
            {
                **apply_status_completion_rules(normalize_document(t)),
                "project_id": project_id,
                "created_at": now,
                "updated_at": now,
            }
        )
    if task_docs:
        await db["tasks"].insert_many(task_docs)
    created = await db["projects"].find_one({"_id": ins.inserted_id})
    return {"id": str(created["_id"]), "name": created["name"], "status": created.get("status", "On Track")}


@router.post("/catalog/{template_id}/create-project")
async def create_project_from_template(template_id: str, payload: dict) -> dict:
    base_name = str(payload.get("name") or "").strip()
    if not base_name:
        raise HTTPException(status_code=400, detail="name is required")
    template = next((t for t in TEMPLATE_CATALOG if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    project = await _create_project_from_template(template, base_name)
    return {"status": "ok", "project": project}


@router.post("/solution-sets/{solution_set_id}/create-projects")
async def create_projects_from_solution_set(solution_set_id: str, payload: dict) -> dict:
    prefix = str(payload.get("name_prefix") or "").strip()
    if not prefix:
        raise HTTPException(status_code=400, detail="name_prefix is required")
    sset = next((s for s in SOLUTION_SETS if s["id"] == solution_set_id), None)
    if not sset:
        raise HTTPException(status_code=404, detail="Solution set not found")
    created = []
    for tid in sset["template_ids"]:
        t = next((x for x in TEMPLATE_CATALOG if x["id"] == tid), None)
        if not t:
            continue
        created.append(await _create_project_from_template(t, f"{prefix} - {t['name']}"))
    return {"status": "ok", "created_projects": created}

