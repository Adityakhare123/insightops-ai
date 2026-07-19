from datetime import UTC, datetime

from fastapi import APIRouter

from apps.api.app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service="insightops-api",
        version="0.1.0",
        timestamp=datetime.now(UTC),
    )
