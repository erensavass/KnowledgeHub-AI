from fastapi import APIRouter

from app.api.v1.schemas.system import VersionResponse
from app.core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/version", response_model=VersionResponse)
def version() -> VersionResponse:
    """Return the running application version without exposing internal metadata."""
    settings = get_settings()
    return VersionResponse(name=settings.app_name, version=settings.app_version)
