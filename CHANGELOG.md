# Changelog

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
