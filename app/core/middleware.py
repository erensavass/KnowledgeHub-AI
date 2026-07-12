import re
import time
from contextvars import ContextVar
from uuid import uuid4

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api.errors import error_body
from app.core.config import Settings
from app.core.logging import get_logger
from app.core.metrics import metrics
from app.core.rate_limit import RedisRateLimiter
from app.core.security import decode_access_token
from app.infrastructure.cache.redis import get_redis_client

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
logger = get_logger(__name__)
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if SAFE_REQUEST_ID.fullmatch(supplied) else str(uuid4())
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            request_id_context.reset(token)
        response.headers["X-Request-ID"] = request_id
        metrics.increment("knowledgehub_http_requests_total")
        metrics.increment("knowledgehub_http_request_duration_milliseconds_total", duration_ms)
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault("Cache-Control", "no-store")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self.limiter = RedisRateLimiter(
            get_redis_client(), settings.rate_limit_window_seconds, settings.rate_limit_fail_open
        )

    def _rule(self, request: Request) -> tuple[str, int, str] | None:
        if request.method != "POST":
            return None
        path = request.url.path
        if path in {"/auth/login", "/auth/register"}:
            principal = request.client.host if request.client else "unknown"
            return "auth", self.settings.auth_rate_limit, principal
        mapping = {
            "/documents/upload": ("upload", self.settings.upload_rate_limit),
            "/search": ("search", self.settings.search_rate_limit),
            "/rag/answer": ("rag", self.settings.rag_rate_limit),
        }
        scope_limit = mapping.get(path)
        if scope_limit is None and path.endswith("/messages/stream"):
            scope_limit = ("stream", self.settings.stream_rate_limit)
        if scope_limit is None:
            return None
        authorization = request.headers.get("Authorization", "")
        if not authorization.lower().startswith("bearer "):
            return None
        try:
            principal = str(decode_access_token(authorization[7:].strip()))
        except jwt.PyJWTError:
            return None
        return scope_limit[0], scope_limit[1], principal

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rule = self._rule(request) if self.settings.rate_limit_enabled else None
        if rule is not None:
            scope, limit, principal = rule
            decision = self.limiter.check(scope, principal, limit)
            if not decision.allowed:
                metrics.increment("knowledgehub_rate_limited_requests_total")
                return JSONResponse(
                    status_code=429,
                    content=error_body("rate_limit_exceeded", "Too many requests; try again later"),
                    headers={"Retry-After": str(decision.retry_after)},
                )
        return await call_next(request)
