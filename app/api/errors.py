from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def add_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        code = "request_error"
        message = str(detail)
        if isinstance(detail, dict):
            code = detail.get("code", code)
            message = detail.get("message", "Request failed")
        logger.warning(
            "http_request_failed",
            extra={
                "error_category": "client" if exc.status_code < 500 else "dependency",
                "error_code": code,
                "method": request.method,
                "path": request.url.path,
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
            headers=exc.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(part) for part in error["loc"][1:]), "message": error["msg"]}
            for error in exc.errors()
        ]
        logger.warning(
            "request_validation_failed",
            extra={
                "error_category": "validation",
                "method": request.method,
                "path": request.url.path,
            },
        )
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", "Request validation failed", details),
        )

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unexpected_request_failure",
            extra={
                "error_category": "internal",
                "exception_type": type(exc).__name__,
                "method": request.method,
                "path": request.url.path,
            },
        )
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "The request could not be completed"),
        )
