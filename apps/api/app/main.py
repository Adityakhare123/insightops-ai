from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.api.v1.router import api_router
from apps.api.app.core.config import settings

app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    description="InsightOps AI backend API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "name": settings.project_name,
        "status": "running",
        "docs": "/docs",
    }
