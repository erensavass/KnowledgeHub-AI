# Enterprise RAG Assistant

An enterprise-ready foundation for a Retrieval-Augmented Generation platform. Sprint 6 adds reliable Milvus vector persistence, compensation, and reconciliation on top of secure document processing.

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

## Included through Sprint 6

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
- Vector cleanup on document reprocessing and deletion
- PostgreSQL document metadata and UUID-based local file storage
- Extension, MIME, content, empty-file, and configurable size validation
- Consistent structured validation and authentication errors
- Typed, environment-based settings management
- Structured JSON application logging to standard output
- SQLAlchemy 2 database session infrastructure and Alembic migration baseline
- Redis client infrastructure with lifecycle cleanup
- Docker Compose stack: FastAPI, PostgreSQL 16, Redis 7, Milvus Standalone, and Nginx
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

3. Verify the service through Nginx:

   ```sh
   curl http://localhost:8000/health
   # {"status":"ok"}

   curl http://localhost:8000/version
   # {"name":"Enterprise RAG Assistant","version":"0.3.0"}
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
   ```

Nginx publishes the API and Milvus publishes its gRPC port (`MILVUS_PORT`, default `19530`) for local administration and integration tests. PostgreSQL, Redis, etcd, and MinIO remain private to the Compose network. The API container waits for dependency health checks and runs `alembic upgrade head` before starting.

Milvus Standalone is resource-intensive. Allocate at least 8 GB RAM to Docker Desktop (16 GB is preferable for sustained workloads), at least 4 CPU cores, and SSD-backed storage. The first BGE-M3 request also downloads model weights and adds its own memory and disk requirements.

## Architecture

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
```

## Configuration

All supported variables are documented in [`.env.example`](.env.example). `SECRET_KEY` is required and must contain at least 32 random characters; generate one with `openssl rand -hex 32`. Access tokens default to 30 minutes and can be shortened with `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`.

Uploads default to `/data/documents` inside the API container's dedicated `document_storage` volume. Configure the location with `DOCUMENT_STORAGE_PATH` and the size ceiling with `MAX_UPLOAD_SIZE_MB` (default: 20). The original client filename is retained only as sanitized metadata; physical files always use generated UUID names. Back up the document volume together with PostgreSQL. Production deployments must inject secrets through the deployment platform rather than committing a `.env` file.

Chunking defaults to `CHUNK_SIZE=1000` characters and `CHUNK_OVERLAP=150`. Overlap preserves whole trailing paragraphs when they fit; oversized individual paragraphs use character-window overlap. Token counts use a stable Unicode word-and-punctuation approximation isolated behind `TokenCounter`, rather than a model-specific tokenizer.

Embeddings default to `EMBEDDING_MODEL=BAAI/bge-m3`, `EMBEDDING_DEVICE=cpu`, `EMBEDDING_BATCH_SIZE=32`, and `EMBEDDING_DIMENSION=1024`. The model is loaded only when embedding is first requested. BGE-M3 is substantial and its first use may download model weights.

Milvus defaults to `MILVUS_URI=http://milvus:19530`, collection `knowledgehub_chunks`, COSINE distance, and an HNSW index. PostgreSQL stores only embedding metadata; dense vectors live only in Milvus. Existing collections are validated and never silently dropped or recreated when incompatible. Document deletion fails safely with HTTP 503 if vector cleanup cannot be confirmed. Cross-store reconciliation for one document is available internally:

```sh
python -m app.cli.reconcile <document_uuid>
```

PDF extraction reads each page's embedded text layer. Scanned or image-only PDFs require OCR, which is intentionally not included in Sprint 4. Complex PDF layouts, tables, headers, and multi-column reading order are limited by the source PDF and parser. DOCX extraction processes body paragraphs in order; text boxes, drawings, headers, footers, and tracked layout semantics are not extracted.

## Development

Install the development dependencies with your preferred environment manager, then run:

```sh
pytest
ruff check .
docker compose config --quiet
```

The normal suite uses an in-memory vector-store fake. Run the opt-in real Milvus lifecycle test only after the Compose Milvus service is healthy:

```sh
RUN_MILVUS_INTEGRATION=1 MILVUS_URI=http://localhost:19530 pytest -m integration
```

To create a future database revision:

```sh
alembic revision --autogenerate -m "describe change"
```

## Deliberately deferred

Background embedding workers, semantic/vector search, BM25, hybrid search, retrieval, RAG, chat, frontend code, and LLM providers are intentionally out of scope for Sprint 6.
