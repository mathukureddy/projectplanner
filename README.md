### ProjectPlanning application

This app is a simplified Smartsheet-style project planning tool built from the `Prompt` and `SmartSheet_features.md` description.

It has:
- **Backend**: FastAPI + MongoDB (`backend/`)
- **Frontend**: React + Vite (`frontend/`)
- **Template**: `Project-Template.json` served by the backend

---

### Backend (FastAPI)

**Install & run**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # on Windows
pip install -r requirements.txt

set MONGODB_URI=mongodb://localhost:27017
set MONGODB_DB=project_planning

uvicorn main:app --reload
```

The API will be at `http://localhost:8000`.

Key endpoints:
- `GET /health`
- `GET/POST /projects/`
- `GET/PATCH/DELETE /projects/{project_id}`
- `GET/POST /tasks/` (query `project_id`)
- `GET/PATCH/DELETE /tasks/{task_id}`
- `GET /template/project-template` → serves `Project-Template.json`

Run backend tests:

```bash
cd backend
pytest
```

---

### Frontend (React + Vite)

**Install & run**

```bash
cd frontend
npm install
npm run dev
```

By default it expects the backend at `http://localhost:8000`. You can change this via `VITE_API_BASE` env var.

Run frontend tests:

```bash
cd frontend
npm test
```

---

### Template

`Project-Template.json` defines:
- Core columns (Task Name, dates, duration, status, % complete, predecessors, parent task)
- Default views (grid, gantt, card, calendar)
- Example automations (notify on completion, overdue alert)

The idea is that new projects can be created based on this structure and stored in MongoDB via the backend APIs.

