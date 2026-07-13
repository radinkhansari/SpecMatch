"""Structured logging.

Convention (see CONTRIBUTING.md): every log line is a structured event.
Call log_event() with a snake_case event name and keyword context fields —
never log interpolated prose strings directly.
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        fields = getattr(record, "event_fields", None)
        if fields:
            payload.update(fields)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def log_event(logger: logging.Logger, level: int, event: str, **fields: object) -> None:
    """Emit a structured log event.

    `event` is a snake_case identifier (e.g. "ingest_completed"), and all
    context goes into keyword fields, not into the event string.
    """
    logger.log(level, event, extra={"event_fields": fields})
