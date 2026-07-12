import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from app.core.config import get_settings


class SensitiveDataFilter(logging.Filter):
    """Add correlation context and remove accidentally attached sensitive fields."""

    REDACTED_FIELDS = {"query", "prompt", "content", "vector", "embedding", "token", "password"}

    def filter(self, record: logging.LogRecord) -> bool:
        from app.core.middleware import request_id_context

        if not hasattr(record, "request_id"):
            record.request_id = request_id_context.get()
        for field in self.REDACTED_FIELDS:
            if hasattr(record, field):
                setattr(record, field, "[REDACTED]")
        return True


def configure_logging() -> None:
    """Configure structured stdout logging for container-friendly collection."""
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SensitiveDataFilter())
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            rename_fields={"levelname": "level"},
        )
    )
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
