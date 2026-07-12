from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import PlainTextResponse
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.schemas.system import HealthResponse, ReadinessResponse
from app.application.vector_store import VectorStore
from app.core.config import get_settings
from app.core.metrics import metrics
from app.dependencies import get_cache_client, get_database_session, get_vector_store

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
@router.get("/live", response_model=HealthResponse)
def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
def readiness(
    response: Response,
    session: Annotated[Session, Depends(get_database_session)],
    cache: Annotated[Redis, Depends(get_cache_client)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
) -> ReadinessResponse:
    settings = get_settings()
    checks: dict[str, str] = {}
    try:
        session.execute(text("SELECT 1"))
        checks["postgresql"] = "ok"
    except Exception:
        checks["postgresql"] = "unavailable"
    try:
        cache.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
    try:
        checks["milvus"] = "ok" if vector_store.health_check() else "unavailable"
    except Exception:
        checks["milvus"] = "unavailable"
    try:
        with httpx.Client(timeout=settings.dependency_health_timeout_seconds) as client:
            ollama = client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            checks["ollama"] = "ok" if ollama.is_success else "unavailable"
    except httpx.HTTPError:
        checks["ollama"] = "unavailable"
    ready = all(value == "ok" for value in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ready" if ready else "not_ready", dependencies=checks)


@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    return metrics.render()
