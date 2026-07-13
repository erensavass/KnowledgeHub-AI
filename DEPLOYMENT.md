# Production deployment

The supplied Compose stack is a single-host reference deployment. For production, copy `.env.production.example` into a secret-managed environment, generate secrets with `openssl rand -hex 32`, set the public domain in `TRUSTED_HOSTS` and the exact HTTPS origin in `CORS_ALLOWED_ORIGINS`, then validate with `docker compose config --quiet` before startup.

Put a TLS-capable load balancer or reverse proxy in front of edge Nginx. Forward the original host/protocol and client address only from trusted proxy hops. The API image accepts forwarded headers from its private container network so authentication limits see the client address; never publish the API container directly or attach untrusted workloads to that network. Redirect port 80 to HTTPS and set HSTS at that TLS boundary after confirming every subdomain supports HTTPS. Do not publish database, Redis, etcd, MinIO, Milvus, or Ollama ports publicly; the Milvus/Ollama host mappings in the development Compose file should be removed or firewalled in production.

Start with `docker compose up -d --build`, pull the configured Ollama model, then check `/live`, `/ready`, `/metrics`, container health, logs, and the browser flow. The API waits for storage dependencies and runs Alembic migrations before serving. Health checks, restart policies, persistent named volumes, proxy timeouts, upload limits, gzip, SSE buffering controls, and an API resource ceiling are included. Tune CPU/memory for the embedding model and Ollama based on measured load; 16 GB host RAM is a practical starting point.

The reference API image installs its lock-aligned PyTorch release from PyTorch's CPU wheel index. GPU deployments must deliberately provide and validate a separate compatible image rather than inheriting CUDA packages through dependency resolution.

Embedding model files persist in the `embedding_model_cache` volume. Prewarm the configured model after the first deployment, or after intentionally changing `EMBEDDING_MODEL`, before admitting user traffic:

```sh
docker compose exec api python -c "from app.dependencies import get_embedding_service; get_embedding_service().embed(['readiness warmup'])"
```

The prewarm avoids placing a multi-gigabyte first-time model transfer inside a bounded HTTP request. Backing up this cache is optional because it can be reconstructed from the configured model source.

Deployment order is PostgreSQL/Redis/etcd/MinIO, Milvus/Ollama, API migration and API, frontend, then edge Nginx. A failed `/ready` response identifies only dependency names and availability, not credentials or exception details. Keep `/live` for process restarts and `/ready` for traffic admission.

## Release checklist

- Review secrets, host/CORS values, TLS, firewall, volume capacity, and backup freshness.
- Run backend tests/Ruff and frontend typecheck/lint/unit/build/E2E.
- Run Alembic upgrade, one-revision downgrade, and re-upgrade against PostgreSQL.
- Run dependency vulnerability and license reviews.
- Verify upload-to-citation and SSE flows through Nginx with two isolated users.
- Restore backups in a disposable environment and run reconciliation.
- Record image digests, release tag, migration revision, and rollback owner.

Rollback application images first. Database downgrade is supported one revision at a time but must be rehearsed and backed up; never downgrade after new-version writes unless the release notes explicitly permit it.
