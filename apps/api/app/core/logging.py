"""Structured JSON logging with request/job correlation ids."""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
from datetime import UTC, datetime

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
job_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("job_id", default=None)
user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("user_id", default=None)


_ENV = "unknown"
_VERSION = "unknown"

# Field names whose values must never reach logs.
_SECRET_KEYS = ("password", "token", "secret", "authorization", "api_key", "cookie", "private_key", "p256dh")
_CAPABILITY_KEYS = {"auth", "endpoint", "push_endpoint"}
_CONTENT_KEYS = {"prompt", "messages", "request_body", "response_body", "body_text", "input_value"}
_DATABASE_PARAMETERS = re.compile(r"\[parameters:.*?\](?=\n|$)", re.DOTALL)
_URL_CREDENTIALS = re.compile(r"(\b[a-z][a-z0-9+.-]*://)[^\s/@]+:[^\s/@]+@", re.IGNORECASE)
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_API_KEY_VALUE = re.compile(r"\b(?:sk[-_](?:proj-|live_|test_)?|cfat_|re_)[A-Za-z0-9_-]{16,}\b")
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?"
                          r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.DOTALL)
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_PUSH_ENDPOINT = re.compile(r"https://(?:fcm\.googleapis\.com|updates\.push\.services\.mozilla\.com(?:\.cn)?|"
                            r"(?:[a-z0-9-]+\.)?push\.apple\.com|[a-z0-9.-]+\.notify\.windows\.com)/[^\s\"'<>]+", re.I)


def _redact_text(value: str) -> str:
    """Provider exceptions and database tracebacks are strings rather than named secret fields."""
    value = _DATABASE_PARAMETERS.sub("[parameters: [redacted]]", value)
    value = _PRIVATE_KEY.sub("[redacted private key]", value)
    value = _URL_CREDENTIALS.sub(r"\1[redacted]@", value)
    value = _BEARER.sub("Bearer [redacted]", value)
    value = _API_KEY_VALUE.sub("[redacted key]", value)
    value = _PUSH_ENDPOINT.sub("[redacted push endpoint]", value)
    return _JWT.sub("[redacted session token]", value)


def _redact_value(value):
    if isinstance(value, dict):
        return _redact(value)
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    return _redact_text(value) if isinstance(value, str) else value


def _redact(fields: dict) -> dict:
    return {k: ("[redacted]" if any(s in str(k).lower().replace("-", "_") for s in _SECRET_KEYS)
                or str(k).lower().split(".")[-1] in _CONTENT_KEYS | _CAPABILITY_KEYS else _redact_value(v)) for k, v in fields.items()}


def redact_sentry_event(event: dict, hint: dict) -> dict:
    """Apply the same privacy boundary to external error reporting and trace events."""
    cleaned = _redact(event)
    request = cleaned.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
    # Exception locals can include entire uploaded files or AI request objects under arbitrary names.
    for value in (cleaned.get("exception") or {}).get("values", []):
        for frame in (value.get("stacktrace") or {}).get("frames", []):
            frame.pop("vars", None)
    return cleaned


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": _redact_text(record.getMessage()),
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
            data["exc"] = _redact_text(self.formatException(record.exc_info))
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
