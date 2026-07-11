from fastapi import APIRouter, status

from app.api.v1.schemas.system import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
def health_check() -> HealthResponse:
    """Liveness probe; dependency readiness is handled by container health checks."""
    return HealthResponse(status="ok")
