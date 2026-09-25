"""Structured JSON logging with request/job correlation ids."""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
job_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("job_id", default=None)
user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("user_id", default=None)


_ENV = "unknown"
_VERSION = "unknown"

# Field names whose values must never reach logs.
_SECRET_KEYS = ("password", "token", "secret", "authorization", "api_key", "cookie")


def _redact(fields: dict) -> dict:
    return {k: ("[redacted]" if any(s in k.lower() for s in _SECRET_KEYS) else v) for k, v in fields.items()}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "env": _ENV,
            "version": _VERSION,
        }
        for key, var in (("request_id", request_id_var), ("job_id", job_id_var), ("user_id", user_id_var)):
            if (v := var.get()) is not None:
                data[key] = v
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            data.update(_redact(extra))
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


def configure_logging(level: str = "INFO", *, environment: str | None = None, version: str | None = None) -> None:
    global _ENV, _VERSION
    _ENV, _VERSION = environment or _ENV, version or _VERSION
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("httpx", "httpcore", "httpx2", "urllib3", "botocore", "PIL", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log(logger: logging.Logger, level: int, msg: str, exc_info: bool = False, **fields) -> None:
    logger.log(level, msg, exc_info=exc_info, extra={"extra_fields": fields})
