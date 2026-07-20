from fastapi import APIRouter

from apps.api.app.api.v1 import health
from apps.api.app.api.v1.endpoints.auth import router as auth_router


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