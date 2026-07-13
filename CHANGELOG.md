# Changelog

## v1.0.0 - 2026-07-13

### Fixed

- API container builds install the lock-aligned PyTorch release from the CPU wheel index, avoiding unintended CUDA runtime packages in CPU deployments.
- The stable CPU runtime layer is cached independently from application source changes.
- Milvus now receives the configured MinIO credentials, and Nginx container probes use an explicit IPv4 loopback address.
- New Milvus collections use strong consistency so acknowledged vector writes are immediately visible to verification and search.
- BGE model downloads persist in a dedicated cache volume, with a documented deployment prewarm step that keeps first-use downloads outside bounded HTTP requests.
- Persistent API volume ownership is initialized before the unprivileged API process starts.
- The frontend development proxy preserves the `/api` prefix required by the Nginx edge,
  allowing real-backend browser validation to reach API routes.
- Removed stale generated Vite configuration artifacts that could shadow the checked-in
  TypeScript proxy configuration during browser validation.

### Validation

- Validated the complete Docker stack, PostgreSQL migration cycle, Redis, real Milvus,
  real Ollama generation, RAG, SSE streaming, persistent conversations, mocked and real
  Playwright journeys, restart persistence, deletion cleanup, and reconciliation.
- Passed 116 backend tests, 22 frontend tests, Ruff, TypeScript, frontend lint and build,
  Docker Compose validation, and Python/npm dependency audits.

## v0.8.0

### Added

- Redis-backed configurable rate limiting for authentication, uploads, search, RAG, and streaming, with hashed principals and `Retry-After`
- Correlation IDs, structured request latency logging, error categories, dependency readiness, process liveness, and Prometheus-compatible counters
- Composite indexes for owner-scoped documents/conversations and conversation-message pagination
- Strict trusted-host and CORS configuration, API security headers, edge CSP, compression, health checks, timeouts, and API resource limits
- Frontend top-level error boundary with safe recovery UI and regression coverage
- Production environment template, threat model, architecture, deployment, backup/recovery, incident runbook, troubleshooting, and release checklist

### Security

- Rate-limit keys contain SHA-256 principal digests rather than IP addresses, user IDs, emails, or bearer tokens
- Request IDs are length/character validated before log propagation and sensitive structured log fields are redacted
- Readiness and client errors report bounded dependency/error categories without internal exception details
- Production guidance now covers TLS, secret management, network isolation, token-storage risk, restore validation, and reconciliation

### Validation note

- The Docker daemon was unavailable during release validation, so real PostgreSQL, Redis, Milvus, Ollama, Nginx, and full-stack browser checks could not run. Per the release gate, this is `v0.8.0`, not `v1.0.0`.

## v0.7.0

### Added

- Production React 18, TypeScript, Vite, and Tailwind frontend
- Tab-scoped JWT authentication with restoration, protected routing, and global 401 handling
- Document upload progress and processing, embedding, status, and deletion workflows
- Conversation management and responsive grounded-chat workspace
- Authenticated POST streaming with incremental SSE parsing, cancellation, and idempotency
- Safe ordered citation panels and embedded-document selection
- Semantic search workspace without answer generation
- Accessible responsive light/dark interface and focus-managed destructive dialogs
- Vitest/Testing Library coverage and mocked Playwright browser journey
- Multi-stage frontend image, SPA Nginx serving, edge API/SSE routing, and frontend CI

## v0.6.0

### Added

- Owner-scoped persistent conversations, messages, and message citations
- Conversation rename, archive, unarchive, pagination, and cascade deletion APIs
- Non-streaming persisted RAG messages with bounded, injection-resistant history
- Server-Sent Events for grounded streaming responses and finalized citations
- Ollama NDJSON and OpenAI SSE streaming provider adapters
- Atomic assistant-message and citation completion with safe failed-message state
- Conversation-scoped database idempotency keys and replay handling
- Configurable title, message, history, pagination, and heartbeat safeguards
- Alembic migration plus opt-in real Ollama and persistent Milvus/Ollama tests

## v0.5.0

### Added

- Grounded answer generation through authenticated `POST /rag/answer`
- Isolated Ollama and optional OpenAI provider adapters with safe error translation
- Injection-resistant prompt construction with bounded untrusted document context
- Application-assembled citations and source metadata for prompt-selected chunks
- Safe unsupported answers when retrieval or model output cannot support an answer
- Query, context, citation, temperature, and request-timeout safeguards
- Persistent Ollama Compose service and documented model setup
- Opt-in real Ollama and Milvus-plus-Ollama integration tests

## v0.4.0

### Added

- Authenticated semantic retrieval through `POST /search`
- User and optional document scoping for Milvus searches
- Configurable bounded result counts and relevance score thresholds
- PostgreSQL hydration of chunk content and source metadata
- Duplicate and stale-vector protection with reconciliation warnings
- Structured retrieval lifecycle logging without query or content disclosure
- Unit coverage and an opt-in real-Milvus semantic search integration test

## v0.3.0

### Added

- Milvus integration
- Vector persistence
- Collection management
- Compensation logic
- Reconciliation service
