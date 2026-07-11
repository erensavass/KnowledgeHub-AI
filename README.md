# Enterprise RAG Assistant

An enterprise-ready foundation for a Retrieval-Augmented Generation platform. Sprint 3 adds secure, owner-isolated document uploads and metadata persistence while deliberately deferring document processing and AI business logic.

## Included through Sprint 3

- Existing `GET /health` and `GET /version` system endpoints
- Registration, login, and current-user endpoints
- Argon2 password hashing and short-lived JWT access tokens
- PostgreSQL-backed users with an Alembic migration
- Authenticated PDF, DOCX, and UTF-8 TXT uploads
- Owner-scoped document listing, inspection, and deletion
- PostgreSQL document metadata and UUID-based local file storage
- Extension, MIME, content, empty-file, and configurable size validation
- Consistent structured validation and authentication errors
- Typed, environment-based settings management
- Structured JSON application logging to standard output
- SQLAlchemy 2 database session infrastructure and Alembic migration baseline
- Redis client infrastructure with lifecycle cleanup
- Docker Compose stack: FastAPI, PostgreSQL 16, Redis 7, and Nginx
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
   # {"name":"Enterprise RAG Assistant","version":"0.1.0"}
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
   ```

Nginx is the only service published to the host. PostgreSQL and Redis are private to the Compose network. The API container runs `alembic upgrade head` before starting.

## Architecture

The codebase follows Clean Architecture boundaries. Dependencies point inward: HTTP and infrastructure adapters may depend on application/domain layers, while domain code must not depend on FastAPI, SQLAlchemy, or Redis.

```text
app/
├── api/                     HTTP routes, endpoint handlers, and response schemas
├── application/             Use cases and orchestration boundary
├── core/                    Settings and structured logging
├── domain/                  Entities, value objects, and domain rules boundary
├── infrastructure/          Database, Redis, and future repository implementations
├── dependencies.py          FastAPI dependency boundaries for external resources
└── main.py                  Application composition root and lifecycle
alembic/                     Database migration environment and revision history
docker/                      API startup and Nginx deployment configuration
tests/                       Endpoint-level regression tests
```

## Configuration

All supported variables are documented in [`.env.example`](.env.example). `SECRET_KEY` is required and must contain at least 32 random characters; generate one with `openssl rand -hex 32`. Access tokens default to 30 minutes and can be shortened with `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`.

Uploads default to `/data/documents` inside the API container's dedicated `document_storage` volume. Configure the location with `DOCUMENT_STORAGE_PATH` and the size ceiling with `MAX_UPLOAD_SIZE_MB` (default: 20). The original client filename is retained only as sanitized metadata; physical files always use generated UUID names. Back up the document volume together with PostgreSQL. Production deployments must inject secrets through the deployment platform rather than committing a `.env` file.

## Development

Install the development dependencies with your preferred environment manager, then run:

```sh
pytest
ruff check .
```

To create a future database revision:

```sh
alembic revision --autogenerate -m "describe change"
```

## Deliberately deferred

Text extraction, chunking, document processing workers, embeddings, Milvus, RAG, chat, frontend code, and LLM providers are intentionally out of scope for Sprint 3.
