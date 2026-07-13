from pathlib import Path
from uuid import uuid4

from redis.exceptions import ConnectionError

from app.core.metrics import MetricsRegistry
from app.core.rate_limit import RedisRateLimiter
from app.dependencies import get_cache_client


class FakeRedis:
    def __init__(self, values: list[int] | None = None, failure: bool = False) -> None:
        self.values = values or [1, 60]
        self.failure = failure
        self.key = ""

    def eval(self, script: str, keys: int, key: str, window: int) -> list[int]:
        del script, keys, window
        self.key = key
        if self.failure:
            raise ConnectionError("redis unavailable")
        return self.values

    def ping(self) -> bool:
        return True


def test_rate_limiter_hashes_principal_and_allows_within_limit() -> None:
    cache = FakeRedis()
    decision = RedisRateLimiter(cache, 60, True).check("search", "sensitive-user-id", 3)  # type: ignore[arg-type]
    assert decision.allowed is True
    assert "sensitive-user-id" not in cache.key
    assert cache.key.startswith("knowledgehub:rate:search:")


def test_rate_limiter_rejects_with_retry_after() -> None:
    decision = RedisRateLimiter(FakeRedis([4, 27]), 60, True).check("auth", "ip", 3)  # type: ignore[arg-type]
    assert decision.allowed is False
    assert decision.retry_after == 27


def test_rate_limiter_failure_policy_is_configurable() -> None:
    cache = FakeRedis(failure=True)
    assert RedisRateLimiter(cache, 60, True).check("auth", "ip", 3).allowed is True  # type: ignore[arg-type]
    assert RedisRateLimiter(cache, 60, False).check("auth", "ip", 3).allowed is False  # type: ignore[arg-type]


def test_request_id_and_security_headers(client) -> None:
    response = client.get("/health", headers={"X-Request-ID": "release-check-1"})
    assert response.headers["X-Request-ID"] == "release-check-1"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"


def test_unsafe_request_id_is_replaced(client) -> None:
    response = client.get("/health", headers={"X-Request-ID": "bad request id\nvalue"})
    assert response.headers["X-Request-ID"] != "bad request id\nvalue"
    assert uuid4().__class__(response.headers["X-Request-ID"])


def test_readiness_reports_dependency_state_without_details(client) -> None:
    client.app.dependency_overrides[get_cache_client] = lambda: FakeRedis()
    response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["dependencies"]["postgresql"] == "ok"
    assert body["dependencies"]["redis"] == "ok"
    assert body["dependencies"]["milvus"] == "ok"
    assert body["dependencies"]["ollama"] == "unavailable"


def test_metrics_are_prometheus_compatible(client) -> None:
    registry = MetricsRegistry()
    registry.increment("knowledgehub_test_total", 2)
    assert registry.render() == (
        "# TYPE knowledgehub_test_total counter\nknowledgehub_test_total 2\n"
    )
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "knowledgehub_http_requests_total" in response.text


def test_api_image_installs_cpu_only_torch() -> None:
    dockerfile = Path("Dockerfile").read_text()
    assert "https://download.pytorch.org/whl/cpu" in dockerfile
    assert "COPY --from=builder /opt/venv /opt/venv" in dockerfile
    assert dockerfile.index('"torch==${TORCH_VERSION}"') < dockerfile.index("COPY app ./app")


def test_compose_health_and_minio_credentials_are_explicit() -> None:
    compose = Path("docker-compose.yml").read_text()
    assert "MINIO_ACCESS_KEY_ID: ${MINIO_ROOT_USER" in compose
    assert "MINIO_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD" in compose
    assert 'http://127.0.0.1/healthz' in compose
    assert "embedding_model_cache:/data/model-cache" in compose
    assert "HF_HOME: ${HF_HOME:-/data/model-cache}" in compose
    assert "api-init:" in compose
    assert 'command: ["chown -R app:app /data/documents /data/model-cache"]' in compose
    assert "condition: service_completed_successfully" in compose


def test_frontend_development_proxy_preserves_edge_api_prefix() -> None:
    vite_config = Path("frontend/vite.config.ts").read_text()
    assert "'/api':" in vite_config
    assert "rewrite:" not in vite_config
    assert not Path("frontend/vite.config.js").exists()
    assert not Path("frontend/vite.config.d.ts").exists()
    assert '"noEmit": true' in Path("frontend/tsconfig.node.json").read_text()


def test_production_environment_template_is_trackable() -> None:
    gitignore = Path(".gitignore").read_text()
    assert "!.env.production.example" in gitignore
    template = Path(".env.production.example").read_text()
    assert "APP_VERSION=1.0.0" in template
    assert "SECRET_KEY=generate-with-openssl-rand-hex-32" in template
