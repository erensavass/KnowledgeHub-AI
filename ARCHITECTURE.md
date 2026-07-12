# Architecture

```text
Browser
  | HTTPS, JWT, SSE
  v
Edge Nginx ----> React static Nginx
  |
  v
FastAPI application
  |---- SQLAlchemy/Alembic ----> PostgreSQL (identity, documents, chunks, conversations)
  |---- redis-py -------------> Redis (rate-limit windows)
  |---- pymilvus -------------> Milvus -> etcd + MinIO (dense vectors)
  |---- sentence-transformers -> BGE-M3 embeddings
  `---- provider adapter ------> Ollama or explicitly configured OpenAI

FastAPI ----> document_storage volume (UUID-named source files)
```

HTTP adapters validate requests and establish the authenticated user. Application services implement extraction, deterministic chunking, embedding, retrieval, prompting, RAG, conversation history, and reconciliation. Infrastructure adapters own PostgreSQL, Redis, Milvus, and model-provider details. PostgreSQL is the source of truth for ownership and source hydration; Milvus results are always scoped by user and revalidated during PostgreSQL hydration.

Request IDs flow through response headers and JSON logs. Metrics use process-local counters without user, query, filename, or document labels. Readiness probes PostgreSQL, Redis, Milvus, and Ollama; liveness checks only the API process.

Consistency boundaries are explicit: embedding writes Milvus before PostgreSQL metadata and compensates on failure; stale vector references are omitted and logged for reconciliation. Conversation assistant content and application-generated citation snapshots commit together after successful generation. Client disconnects do not persist partial assistant answers.

See [SECURITY.md](SECURITY.md) for trust boundaries and [DEPLOYMENT.md](DEPLOYMENT.md) for the production topology.
