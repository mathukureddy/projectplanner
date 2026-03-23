from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import asyncio

from routes import alerts, attachments, comments, projects, tasks, template, automations, reports, data_features, integrations, auth, intake_forms, workload
from automation_scheduler import scheduler_enabled, start_overdue_scheduler


def create_app() -> FastAPI:
    app = FastAPI(title="ProjectPlanner API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(projects.router, prefix="/projects", tags=["projects"])
    app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
    app.include_router(template.router, prefix="/template", tags=["template"])
    app.include_router(comments.router, prefix="/comments", tags=["comments"])
    app.include_router(attachments.router, prefix="/attachments", tags=["attachments"])
    app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
    app.include_router(automations.router, prefix="/projects", tags=["automations"])
    app.include_router(reports.router, prefix="/reports", tags=["reports"])
    app.include_router(data_features.router, prefix="/projects", tags=["data-features"])
    app.include_router(integrations.router, prefix="/projects", tags=["integrations"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(intake_forms.router, prefix="/projects", tags=["intake-forms"])
    app.include_router(intake_forms.public_router, prefix="/intake", tags=["intake-forms-public"])
    app.include_router(workload.router, prefix="/reports", tags=["workload"])

    if scheduler_enabled():
        @app.on_event("startup")
        async def _start_overdue_scheduler() -> None:
            start_overdue_scheduler(asyncio.get_running_loop())

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

