from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.search import router as search_router
from app.api.v1.endpoints.version import router as version_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(documents_router)
router.include_router(health_router)
router.include_router(search_router)
router.include_router(version_router)
