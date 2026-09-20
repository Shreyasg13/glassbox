"""Structured JSON request logging + a request-id contextvar (Phase 6).

Deliberately logs only method/path/status/duration/request_id -- never
headers or bodies, which would leak the Authorization bearer token or a
provider API key straight into the log stream. See the secrets-hygiene
note in app/providers/gemini.py for the related response-body leak this
project already fixes for the same reason.
"""
from __future__ import annotations

import contextvars
import json
import logging
import sys

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JSONRequestFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "message": record.getMessage()}
        for key in ("method", "path", "status_code", "duration_ms", "request_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)


def quiet_http_clients() -> None:
    """httpx logs every request line at INFO, URL included -- and Gemini takes its API key
    as a `?key=` query parameter, so the key landed in the container log (and anything that
    ships it). Warnings and errors still come through; they carry no URL."""
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def setup_logging() -> logging.Logger:
    quiet_http_clients()
    logger = logging.getLogger("glassbox.request")
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONRequestFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
