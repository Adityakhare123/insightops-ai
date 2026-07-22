from fastapi import APIRouter

from apps.api.app.api.v1 import health
from apps.api.app.api.v1.endpoints.auth import (
    router as auth_router,
)
from apps.api.app.api.v1.endpoints.documents import (
    router as documents_router,
)
from apps.api.app.api.v1.endpoints.rag import (
    router as rag_router,
)
from apps.api.app.api.v1.endpoints.sql_agent import (
    router as sql_agent_router,
)


api_router = APIRouter()

api_router.include_router(
    health.router,
    tags=["health"],
)

api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["authentication"],
)

api_router.include_router(
    documents_router,
    prefix="/documents",
    tags=["documents"],
)

api_router.include_router(
    rag_router,
    prefix="/rag",
    tags=["rag"],
)

api_router.include_router(
    sql_agent_router,
    prefix="/sql-agent",
    tags=["sql-agent"],
)