# KnowledgeHub AI

An enterprise-ready Retrieval-Augmented Generation platform with a production React interface over the secure document, search, and conversation APIs.

## v0.8.0

Sprint 11 hardens the release candidate with Redis-backed per-IP and per-user rate limits, request correlation and latency logs, dependency readiness and process liveness, Prometheus-compatible counters, strict host/CORS and security headers, production configuration, query-driven database indexes, frontend crash recovery, and operations/security/deployment documentation. The fallback version is used because the required real Docker full-stack validation could not run while the Docker daemon was unavailable; this release is not represented as v1.0.0.

## v0.7.0

Sprint 10 adds a React 18 and TypeScript frontend with protected authentication, document lifecycle management, semantic search, persistent conversations, authenticated POST-based SSE streaming, safe citations, cancellation, responsive navigation, and light/dark presentation. The production stack serves immutable frontend assets through a dedicated Nginx container and keeps all existing API routes available.

## v0.6.0

Conversations now persist user questions, completed grounded answers, generation status, request IDs, and application-generated citations. Both regular and SSE message endpoints reuse the existing user-scoped retrieval and RAG pipeline. Historical messages are bounded, escaped, and supplied as untrusted data in a block separate from retrieved documents.

## v0.5.0

`POST /rag/answer` retrieves only the authenticated user's embedded chunks, places bounded untrusted context into an injection-resistant prompt, and generates an answer through local Ollama by default. Citations are assembled by the application from the exact chunks included in the prompt. OpenAI is an optional provider and is not configured or contacted unless selected.

## v0.4.0

Semantic retrieval is available through `POST /search`, with mandatory user scoping, optional document filters, bounded result counts, score thresholds, PostgreSQL source hydration, and safe handling of stale vector references. This release does not call an LLM or generate answers.

## v0.3.0

Milvus integration adds stable chunk-vector identities, idempotent collection management, vector lifecycle cleanup, cross-store compensation, and an internal reconciliation command. Semantic search and retrieval remain deliberately out of scope.

## v0.2.0

Implemented the document processing pipeline:

- Secure authentication
- Document upload
- PDF, DOCX, and TXT extraction
- Deterministic chunking
- Processing lifecycle

Sprint 5 added lazy, CPU-compatible chunk embedding generation with PostgreSQL metadata tracking.

## Included through Sprint 11

- Existing `GET /health` and `GET /version` system endpoints
- Registration, login, and current-user endpoints
- Argon2 password hashing and short-lived JWT access tokens
- PostgreSQL-backed users with an Alembic migration
- Authenticated PDF, DOCX, and UTF-8 TXT uploads
- Owner-scoped document listing, inspection, and deletion
- PDF page-by-page, DOCX paragraph-order, and validated UTF-8 TXT extraction
- Deterministic, paragraph-aware chunking with configurable overlap
- Persisted chunk metadata, owner-scoped pagination, and cascade deletion
- Transaction-safe processing and reprocessing with safe failure codes
- Lazy `sentence-transformers` embedding generation using `BAAI/bge-m3` by default
- Per-chunk embedding model and dimension metadata without PostgreSQL vector storage
- Owner-scoped embedding execution, force re-embedding, and lifecycle status reporting
- Milvus Standalone vector persistence with stable chunk UUID primary keys
- Idempotent schema/index validation using COSINE and HNSW defaults
- PostgreSQL/Milvus compensation and reconciliation support
- Authenticated, user-scoped semantic retrieval with optional document filtering
- Ordered PostgreSQL hydration of retrieved chunk content and source metadata
- Grounded RAG answer generation using Ollama or optional OpenAI
- Application-controlled citations with bounded source excerpts
- Safe unsupported answers and document prompt-injection defenses
- Persistent owner-scoped conversations, messages, and citation snapshots
- Bounded injection-resistant conversation history
- Idempotent message creation within each conversation
- Ollama and OpenAI streaming through Server-Sent Events
- React, TypeScript, Vite, Tailwind, React Router, and TanStack Query frontend
- Responsive authenticated document, search, conversation, and chat workspaces
- Incremental fetch-stream SSE rendering with cancellation and idempotency
- Accessible plain-text citations, focus-managed dialogs, and dark mode
- Vector cleanup on document reprocessing and deletion
- PostgreSQL document metadata and UUID-based local file storage
- Extension, MIME, content, empty-file, and configurable size validation
- Consistent structured validation and authentication errors
- Typed, environment-based settings management
- Structured JSON application logging to standard output
- Correlated request IDs, request latency logs, readiness/liveness, and safe metrics
- Redis-backed configurable authentication, upload, search, RAG, and streaming limits
- SQLAlchemy 2 database session infrastructure and Alembic migration baseline
- Redis client infrastructure with lifecycle cleanup
- Docker Compose stack: React static frontend, FastAPI, PostgreSQL 16, Redis 7, Milvus Standalone, Ollama, and edge Nginx
- MIT licensing, test scaffolding, and repository hygiene

## Quick start

1. Create your local environment file:

   ```sh
   cp .env.example .env
   ```

2. Replace all placeholder secrets in `.env`, then start the stack:

   ```sh
   docker compose up --build
   ```

3. Open the application at `http://localhost:8000`, or verify the API through Nginx:

   ```sh
   curl http://localhost:8000/health
   # {"status":"ok"}

   curl http://localhost:8000/version
   # {"name":"KnowledgeHub AI","version":"0.8.0"}
   ```

4. Register, log in, and access protected endpoints:

   ```sh
   curl -X POST http://localhost:8000/auth/register \
     -H 'Content-Type: application/json' \
     -d '{"email":"person@example.com","password":"StrongPass123!"}'

   curl -X POST http://localhost:8000/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"email":"person@example.com","password":"StrongPass123!"}'

   curl http://localhost:8000/auth/me -H 'Authorization: Bearer <access_token>'

   curl -X POST http://localhost:8000/documents/upload \
     -H 'Authorization: Bearer <access_token>' \
     -F 'file=@report.pdf;type=application/pdf'

   curl http://localhost:8000/documents \
     -H 'Authorization: Bearer <access_token>'

   curl -X POST http://localhost:8000/documents/<document_id>/process \
     -H 'Authorization: Bearer <access_token>'

   curl 'http://localhost:8000/documents/<document_id>/chunks?limit=50&offset=0' \
     -H 'Authorization: Bearer <access_token>'

   curl -X POST 'http://localhost:8000/documents/<document_id>/embed?force=false' \
     -H 'Authorization: Bearer <access_token>'

   curl http://localhost:8000/documents/<document_id>/embedding-status \
     -H 'Authorization: Bearer <access_token>'

   curl -X POST http://localhost:8000/search \
     -H 'Authorization: Bearer <access_token>' \
     -H 'Content-Type: application/json' \
     -d '{"query":"How does authentication work?","top_k":5,"score_threshold":0.0}'

   curl -X POST http://localhost:8000/rag/answer \
     -H 'Authorization: Bearer <access_token>' \
     -H 'Content-Type: application/json' \
     -d '{"query":"How does authentication work?","top_k":5,"score_threshold":0.0}'

   curl -X POST http://localhost:8000/conversations \
     -H 'Authorization: Bearer <access_token>' \
     -H 'Content-Type: application/json' \
     -d '{"title":"Security questions"}'

   curl -X POST http://localhost:8000/conversations/<conversation_id>/messages \
     -H 'Authorization: Bearer <access_token>' \
     -H 'Idempotency-Key: question-001' \
     -H 'Content-Type: application/json' \
     -d '{"query":"How does authentication work?"}'

   curl -N -X POST http://localhost:8000/conversations/<conversation_id>/messages/stream \
     -H 'Authorization: Bearer <access_token>' \
     -H 'Content-Type: application/json' \
     -d '{"query":"Summarize the token lifecycle."}'
   ```

Nginx publishes the React SPA and preserves the existing root API routes. The frontend uses `/api`, which the edge proxy strips before forwarding to FastAPI; buffering is disabled for SSE. Milvus publishes its gRPC port (`MILVUS_PORT`, default `19530`) for local administration and integration tests. PostgreSQL, Redis, etcd, and MinIO remain private to the Compose network. The API container waits for dependency health checks and runs `alembic upgrade head` before starting.

Milvus Standalone and local generation are resource-intensive. Allocate at least 8 GB RAM to Docker Desktop (16 GB is preferable for sustained workloads), at least 4 CPU cores, and SSD-backed storage. The first BGE-M3 request also downloads model weights and adds its own memory and disk requirements.

Ollama starts without assuming a model is already present. Pull the configured model once after the service is healthy; model data is retained in the `ollama_data` volume:

```sh
docker compose exec ollama ollama pull llama3.1:8b
```

A missing model produces a bounded provider error for RAG requests and does not make the Ollama health check wait forever.

## Architecture

The complete component diagram, consistency boundaries, and data ownership model are in [ARCHITECTURE.md](ARCHITECTURE.md). Production topology and release checks are in [DEPLOYMENT.md](DEPLOYMENT.md), security assumptions are in [SECURITY.md](SECURITY.md), backup, recovery, incident, and troubleshooting procedures are in [docs/runbook.md](docs/runbook.md), and the latest dependency review is in [docs/dependency-audit.md](docs/dependency-audit.md).

The codebase follows Clean Architecture boundaries. Dependencies point inward: HTTP and infrastructure adapters may depend on application/domain layers, while domain code must not depend on FastAPI, SQLAlchemy, or Redis.

```text
app/
├── api/                     HTTP routes, endpoint handlers, and response schemas
├── application/             Use cases and orchestration boundary
├── core/                    Settings and structured logging
├── domain/                  Entities, value objects, and domain rules boundary
├── infrastructure/          PostgreSQL, Redis, and Milvus adapters
├── dependencies.py          FastAPI dependency boundaries for external resources
└── main.py                  Application composition root and lifecycle
alembic/                     Database migration environment and revision history
docker/                      API startup and Nginx deployment configuration
tests/                       Endpoint-level regression tests
frontend/                    React application, static Nginx image, unit and browser tests
```

The frontend keeps JWTs in memory and `sessionStorage` to restore `/auth/me` after refresh within the same tab. This is less persistent than `localStorage`, but any script running in the origin can still access the token; production deployments must maintain a strict Content Security Policy, avoid untrusted scripts, and address XSS as a credential risk. Tokens are never placed in URLs or logs.

TanStack Query owns server state. Local component state is limited to transient UI concerns such as the mobile drawer, selected documents, and the active streamed answer. SSE is parsed from authenticated `fetch` response bytes so partial frames, POST bodies, bearer headers, idempotency keys, and `AbortController` cancellation are supported.

## Configuration

All supported variables are documented in [`.env.example`](.env.example). `SECRET_KEY` is required and must contain at least 32 random characters; generate one with `openssl rand -hex 32`. Access tokens default to 30 minutes and can be shortened with `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`.

Production deployments must start from [`.env.production.example`](.env.production.example), replace every placeholder, set exact trusted hosts and CORS origins, and keep the populated file out of version control. Rate-limit windows and route-class limits are configurable. Auth limits use a hashed client-address principal; protected route limits use a hashed authenticated user ID. Redis outages fail open by default with a structured warning to preserve service availability; set `RATE_LIMIT_FAIL_OPEN=false` where availability policy requires fail-closed behavior.

Uploads default to `/data/documents` inside the API container's dedicated `document_storage` volume. Configure the location with `DOCUMENT_STORAGE_PATH` and the size ceiling with `MAX_UPLOAD_SIZE_MB` (default: 20). The original client filename is retained only as sanitized metadata; physical files always use generated UUID names. Back up the document volume together with PostgreSQL. Production deployments must inject secrets through the deployment platform rather than committing a `.env` file.

Chunking defaults to `CHUNK_SIZE=1000` characters and `CHUNK_OVERLAP=150`. Overlap preserves whole trailing paragraphs when they fit; oversized individual paragraphs use character-window overlap. Token counts use a stable Unicode word-and-punctuation approximation isolated behind `TokenCounter`, rather than a model-specific tokenizer.

Embeddings default to `EMBEDDING_MODEL=BAAI/bge-m3`, `EMBEDDING_DEVICE=cpu`, `EMBEDDING_BATCH_SIZE=32`, and `EMBEDDING_DIMENSION=1024`. The model is loaded only when embedding is first requested. BGE-M3 is substantial and its first use may download model weights.

Milvus defaults to `MILVUS_URI=http://milvus:19530`, collection `knowledgehub_chunks`, COSINE distance, and an HNSW index. PostgreSQL stores only embedding metadata; dense vectors live only in Milvus. Existing collections are validated and never silently dropped or recreated when incompatible. Document deletion fails safely with HTTP 503 if vector cleanup cannot be confirmed. Cross-store reconciliation for one document is available internally:

```sh
python -m app.cli.reconcile <document_uuid>
```

Semantic search defaults to five results, is capped at 20, and applies a minimum score of `0.0`. Configure these values with `SEARCH_DEFAULT_TOP_K`, `SEARCH_MAX_TOP_K`, and `SEARCH_SCORE_THRESHOLD`. Only chunks with current PostgreSQL embedding metadata from documents marked embedded are returned. Supplying an unknown or another user's document ID returns HTTP 404.

Grounded generation defaults to `LLM_PROVIDER=ollama`, model `llama3.1:8b`, temperature `0.1`, at most eight context chunks, and a 60-second provider timeout. Context is capped at 24,000 characters, queries at 2,000 characters, and citation excerpts at 300 characters. These limits are configurable through the `LLM_*` and `RAG_*` variables in `.env.example`.

Conversation titles default to `New conversation` and are never generated by an LLM. Lists exclude archived conversations unless `include_archived=true` and use configurable pagination. History defaults to the eight most recent completed messages and 12,000 total characters. It contains message text only—never old citation excerpts, prompts, tokens, or vectors.

`Idempotency-Key` is optional on both message endpoints. Repeating a completed request with the same authenticated user, conversation, and key replays the stored assistant result without inserting messages. A pending or failed key returns HTTP 409; retry with a new key. Keys are enforced in PostgreSQL for one conversation and are not a distributed idempotency service.

The streaming endpoint emits `request_started`, `retrieval_completed`, `token`, `citations`, `completed`, and safe `error` events. Comment heartbeats keep idle SSE connections active. Tokens are transient: the complete assistant message and citations are committed together only after successful generation. Disconnects and failures leave the user message marked failed without a completed partial assistant message.

To use OpenAI for a request, configure `OPENAI_API_KEY` and optionally `OPENAI_MODEL`, then either set `LLM_PROVIDER=openai` or send `"provider":"openai"`. The key is not required for the default Ollama provider and is never included in logs or responses.

PDF extraction reads each page's embedded text layer. Scanned or image-only PDFs require OCR, which is intentionally not included in Sprint 4. Complex PDF layouts, tables, headers, and multi-column reading order are limited by the source PDF and parser. DOCX extraction processes body paragraphs in order; text boxes, drawings, headers, footers, and tracked layout semantics are not extracted.

## Development

Install the development dependencies with your preferred environment manager, then run:

```sh
pytest
ruff check .
docker compose config --quiet
```

System probes are `GET /live` (process only), `GET /ready` (PostgreSQL, Redis, Milvus, and Ollama), and `GET /metrics` (Prometheus text format). Metrics intentionally avoid user, document, filename, prompt, and query labels.

For local frontend development, run FastAPI on port 8000 and configure the browser-accessible API URL:

```sh
cd frontend
cp .env.example .env
npm ci
npm run dev
```

The Vite development server proxies the default `/api` path to FastAPI at `127.0.0.1:8000`, avoiding a separate CORS configuration. In the production image `/api` is handled by edge Nginx. Vite variables are embedded during the build and are not runtime secrets.

Frontend verification and production build:

```sh
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e
```

The normal Playwright journey mocks backend responses. Running against a real backend, Milvus, and Ollama is optional and requires a separately prepared full stack and model:

```sh
RUN_REAL_BACKEND_E2E=1 npm run test:e2e
```

## Screenshots

Screenshots will be added after the first deployed UI review:

- Desktop conversation workspace — _placeholder_
- Mobile document workflow — _placeholder_
- Semantic search and citation panel — _placeholder_

The normal suite uses an in-memory vector-store fake. Run the opt-in real Milvus lifecycle test only after the Compose Milvus service is healthy:

```sh
RUN_MILVUS_INTEGRATION=1 MILVUS_URI=http://localhost:19530 pytest -m integration
```

After pulling the Ollama model, run the two opt-in RAG integration paths with host-accessible service URLs:

```sh
RUN_OLLAMA_INTEGRATION=1 \
OLLAMA_BASE_URL=http://localhost:11434 \
pytest tests/test_rag_integration.py::test_real_ollama_generation

RUN_RAG_E2E_INTEGRATION=1 \
MILVUS_URI=http://localhost:19530 \
OLLAMA_BASE_URL=http://localhost:11434 \
pytest tests/test_rag_integration.py::test_real_milvus_and_ollama_rag_pipeline

RUN_OLLAMA_STREAM_INTEGRATION=1 \
OLLAMA_BASE_URL=http://localhost:11434 \
pytest tests/test_rag_integration.py::test_real_ollama_streaming

RUN_CONVERSATION_E2E_INTEGRATION=1 \
MILVUS_URI=http://localhost:19530 \
OLLAMA_BASE_URL=http://localhost:11434 \
pytest tests/test_rag_integration.py::test_real_persistent_conversation_flow
```

To create a future database revision:

```sh
alembic revision --autogenerate -m "describe change"
```

## Deliberately deferred

Background workers, BM25, hybrid search, multi-tenant administration, agent workflows, WebSocket collaboration, OCR, and automatic conversation-title generation are intentionally out of scope for Sprint 11.

## Limitations

- Answers are only as reliable as the retrieved context and the selected generation model.
- Scanned or image-only PDFs still require OCR before their content can be retrieved.
- Local answer quality and resource usage depend on the selected Ollama model.
- Citations identify retrieved source chunks; they are not formal academic references.
- Streaming uses one-way HTTP Server-Sent Events, not WebSockets.
- Conversation titles remain user-authored; automatic LLM-generated titles are not included.
- Generation runs in the request process without background workers.
- Partial streamed output is not persisted as a completed assistant response.
- Local streaming speed depends heavily on hardware and Ollama model size.
