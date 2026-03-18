from fastapi import APIRouter
from fastapi.responses import FileResponse
from pathlib import Path


router = APIRouter()


@router.get("/project-template", response_class=FileResponse)
async def get_project_template() -> FileResponse:
  base_dir = Path(__file__).resolve().parents[2]
  template_path = base_dir / "Project-Template.json"
  return FileResponse(template_path)

