"""Structured (JSON) logging.

Every log line becomes one JSON object, which log tools (Loki, ELK, CloudWatch...) can
search by field. Set LOG_JSON=false for human readable lines during local development.
Extra fields are attached with `logger.info("msg", extra={"fields": {...}})`.
"""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:<7} {record.name}: {record.getMessage()}"
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict) and fields:
            base += " " + " ".join(f"{k}={v}" for k, v in fields.items())
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.log_json else TextFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    # Uvicorn's own access log duplicates our request log middleware.
    logging.getLogger("uvicorn.access").disabled = True
