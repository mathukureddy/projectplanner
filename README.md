### ProjectPlanner application

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

**Important:** Keep `MONGODB_DB` the same every time you start the backend (or use `backend/.env` — see `backend/.env.example`). If it changes after a restart, MongoDB points at a different database and existing projects will not appear.

```bash
# optional: copy env template
cd backend
copy .env.example .env
```

The API will be at `http://localhost:8000`.

Authentication endpoints:
- `POST /auth/register` (username, email, password, role)
- `POST /auth/login` (username, password)
- `GET /auth/me` (Bearer token)

Admin user management (requires Bearer token with `role: admin` — bootstrap `admin` or a database admin):
- `GET /auth/admin/users` — list database users (bootstrap env-only admin is not listed)
- `POST /auth/admin/users` — create user (`username`, `password`, `role`, optional `email`)
- `PATCH /auth/admin/users/{user_id}` — update `email`, `role`, and/or `password`
- `DELETE /auth/admin/users/{user_id}` — delete user (cannot delete yourself; cannot remove/demote the last DB admin)

Intake forms (Gap 5 — each submission creates a **new task**):
- `GET /projects/{project_id}/intake-forms` — list forms
- `POST /projects/{project_id}/intake-forms` — create form (fields, `task_name_field`, optional mapping fields)
- `GET/PATCH/DELETE /projects/{project_id}/intake-forms/{form_id}`
- `GET /projects/{project_id}/intake-forms/{form_id}/submissions` — recent submissions (audit)
- **Public (no auth):** `GET /intake/public/{slug}` — form schema; `POST /intake/public/{slug}/submit` — body `{ "responses": { "field_key": "..." } }`

Bootstrap local admin login (if no registered user): `admin / admin123`  
Override with env vars:
- `APP_ADMIN_USERNAME`
- `APP_ADMIN_PASSWORD`

Key endpoints:
- `GET /health`
- `GET/POST /projects/`
- `GET/PATCH/DELETE /projects/{project_id}` (PATCH supports `shares: [{ email, role }]`, roles: `viewer` | `editor` | `admin`)
- `POST /projects/{project_id}/baseline/snapshot`
- `GET/POST /tasks/` (query `project_id`)
- `GET/PATCH/DELETE /tasks/{task_id}`
- **Collaboration**
  - `GET/POST /comments/` (query `project_id`; list also needs `task_id`)
  - `DELETE /comments/{comment_id}` (query `project_id`)
  - `GET /attachments/` (query `project_id`, `task_id`)
  - `POST /attachments/upload` (multipart: `project_id`, `task_id`, `file`, optional `uploaded_by`)
  - `GET /attachments/{id}/file` (query `project_id`) — download
  - `DELETE /attachments/{id}` (query `project_id`)
  - `GET /alerts/` (query `project_id`, optional `unread_only`)
  - `POST /alerts/` (JSON: `project_id`, `title`, `message`, optional `task_id`)
  - `PATCH /alerts/{id}` (query `project_id`, body `{ read: true }`)
  - `POST /alerts/scan-overdue` (query `project_id`) — creates unread overdue-task alerts
- `GET /template/project-template` → serves `Project-Template.json`

Task attachments are stored under `backend/uploads/` (gitignored).

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

