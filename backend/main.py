from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import projects, tasks, template


def create_app() -> FastAPI:
    app = FastAPI(title="ProjectPlanning API")

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

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

