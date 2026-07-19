from fastapi import APIRouter

from apps.api.app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
