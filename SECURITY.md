# Security policy

## Reporting

Do not open public issues for suspected vulnerabilities. Send a private report to the repository owner with the affected version, reproduction steps, impact, and suggested mitigation. Do not include live credentials or personal document contents. Supported releases are the latest tagged release only.

## Threat model summary

KnowledgeHub AI assumes mutually untrusted authenticated users and untrusted uploaded files, prompts, retrieved text, filenames, and model output. Principal risks are broken object-level authorization, XSS/token theft, path traversal, malicious document content, prompt injection, denial of service, dependency compromise, and data inconsistency between PostgreSQL, document storage, and Milvus.

Controls include owner predicates on every document, retrieval, and conversation query; UUID physical filenames under a configured storage root; extension/MIME/signature/size validation; short-lived signed JWTs; strict host/CORS allowlists; Redis rate limits; plain React text rendering; CSP and response security headers; bounded prompts/history/output; application-generated citations; parameterized SQL; safe client errors; and log redaction. Retrieved document text is explicitly delimited as untrusted and cannot grant permissions or change system instructions.

Residual risks include browser-readable `sessionStorage` tokens if same-origin script execution is compromised, parser/model resource exhaustion within configured limits, model hallucination, prompt injection influencing answer quality, and Compose secrets supplied as environment variables. Use an external TLS terminator, secret manager, network policy, monitoring, encrypted backups, and single-purpose hosts in production.

## Operator checklist

- Generate unique `SECRET_KEY`, PostgreSQL, MinIO, and external-provider credentials.
- Restrict `TRUSTED_HOSTS` and `CORS_ALLOWED_ORIGINS`; never use `*` with credentials.
- Terminate TLS 1.2+ before Nginx and redirect HTTP to HTTPS; add HSTS only at the TLS terminator.
- Keep PostgreSQL, Redis, MinIO, Milvus, and Ollama off public networks.
- Review `/metrics` exposure and protect it at the infrastructure boundary if required.
- Rotate secrets and invalidate sessions after suspected compromise.
- Run Python and npm audits before each release.
