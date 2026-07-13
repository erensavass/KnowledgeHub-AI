FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /build
COPY pyproject.toml README.md ./
ARG TORCH_VERSION=2.13.0
RUN python -m venv /opt/venv \
    && pip install --index-url https://download.pytorch.org/whl/cpu "torch==${TORCH_VERSION}"
COPY app ./app
RUN pip install .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/opt/venv/bin:$PATH

RUN groupadd --system app && useradd --system --gid app --create-home app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY docker/api/entrypoint.sh /entrypoint.sh
RUN mkdir -p /data/documents \
    && chmod 755 /entrypoint.sh \
    && chown -R app:app /app /data/documents

USER app
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
