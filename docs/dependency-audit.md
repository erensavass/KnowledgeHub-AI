# Dependency audit — 2026-07-13

The Sprint 11 release audit ran against `uv.lock` and `frontend/package-lock.json`.

- `pip-audit` over the frozen production uv export: no known vulnerabilities.
- `npm audit --audit-level=low`: zero vulnerabilities.
- `npm outdated`: no entries at audit time.
- `license-checker --production --summary`: 13 MIT packages and one `UNLICENSED` entry, which is the private local `knowledgehub-frontend` package rather than a redistributed third-party dependency.
- Installed Python metadata review: no detected license conflict. Jinja2, annotated-types, email-validator, markdown-it-py, mdurl, pymilvus, python-dateutil, safetensors, tokenizers, and typing_extensions omit a reliably categorized license expression in the installed metadata and require normal manual notice review before redistribution.

Audit databases and registry state change over time; rerun these checks for every release and when rebuilding images. The audit utility itself emitted deprecation warnings in its transient dependency tree; it is not part of the application lockfile or production image. No major versions were upgraded solely to satisfy “latest” status.
