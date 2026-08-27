from datetime import UTC, datetime

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.schemas.health import (
    HealthResponse,
    ReadinessResponse,
    ServiceStatus,
)
from app.services.health import check_milvus, check_postgres


router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        application=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        timestamp=datetime.now(UTC),
    )


@router.get("/ready", response_model=ReadinessResponse)
def readiness_check(response: Response) -> ReadinessResponse:
    postgres_ok, postgres_detail = check_postgres()
    milvus_ok, milvus_detail = check_milvus()

    ready = postgres_ok and milvus_ok

    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        services={
            "postgres": ServiceStatus(
                status="healthy" if postgres_ok else "unhealthy",
                detail=postgres_detail,
            ),
            "milvus": ServiceStatus(
                status="healthy" if milvus_ok else "unhealthy",
                detail=milvus_detail,
            ),
        },
        timestamp=datetime.now(UTC),
    )