from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import add_error_handlers
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.dependencies import close_vector_store
from app.infrastructure.cache.redis import close_redis
from app.infrastructure.database.session import close_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    logger = get_logger(__name__)
    logger.info("application_started")
    yield
    close_redis()
    close_vector_store()
    close_database()
    logger.info("application_stopped")


def create_application() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.app_debug,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    application.include_router(api_router)
    add_error_handlers(application)
    return application


app = create_application()
