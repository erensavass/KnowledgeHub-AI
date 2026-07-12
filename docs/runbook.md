# Operations runbook

## Routine checks

Check `/live`, `/ready`, `/metrics`, `docker compose ps`, disk space, volume growth, error-category logs, rate-limit warnings, processing/embedding failures, retrieval/RAG failures, and SSE disconnect rates. Correlate a client-visible `X-Request-ID` with structured API logs; never request a user's token, query, or document content for routine diagnosis.

## Backup and restore

Use `pg_dump --format=custom` for PostgreSQL and verify with `pg_restore --list`. Snapshot `document_storage`, `milvus_data`, `milvus_etcd_data`, and `milvus_minio_data` together after quiescing writes; retain Ollama's `ollama_data` only to avoid model re-downloads, not as business data. Encrypt backups, restrict access, record checksums, and rehearse restores.

Restore in this order: PostgreSQL; document storage; Milvus etcd/MinIO/data from the same recovery point; Redis (optional because rate-limit state may be discarded); Ollama model volume or re-pull; then API/frontend/Nginx. Run Alembic to the recorded revision, verify document paths, execute `python -m app.cli.reconcile <document_uuid>` for affected documents, re-embed inconsistencies, and test two-user isolation before reopening traffic.

If PostgreSQL and Milvus recovery points differ, PostgreSQL remains authoritative. Do not expose orphan vectors; hydration already omits them. Reconcile or re-embed documents in controlled batches.

## Incidents and troubleshooting

- `/live` fails: restart API and inspect startup/migration logs.
- `/ready` names a dependency unavailable: check that container, DNS, health, credentials, and disk; do not bypass readiness permanently.
- HTTP 429: inspect scope-level traffic and Redis health; use `Retry-After`, then adjust configured limits only with evidence.
- Upload rejected: check size, exact MIME, file signature, UTF-8/ZIP integrity, and storage capacity.
- Embedding unavailable: verify BGE model cache, memory, configured dimension, and Milvus schema.
- RAG unavailable: verify retrieval first, then Ollama model presence/provider timeout. Never log the prompt to debug it.
- SSE stalls: confirm Nginx buffering is off, proxy timeout exceeds provider timeout, heartbeats pass, and the client has not canceled.
- Missing citations/results after restore: run reconciliation and re-embed; do not manually fabricate metadata.

## Migration drill

Back up first. Against a disposable PostgreSQL database run `alembic upgrade head`, `alembic downgrade -1`, and `alembic upgrade head`, then inspect constraints/indexes and run the full test suite. A SQLite migration check is useful but is not evidence of PostgreSQL compatibility.

## Screenshots

Release screenshots are intentionally not embedded until captured from a fully validated production-like stack. Capture login, library, semantic search, streamed conversation, and citation views without tokens, email addresses, filenames, or document contents.
