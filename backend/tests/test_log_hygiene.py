"""Provider API keys must never reach the logs.

Gemini authenticates with a `?key=` query parameter, and httpx logs each request URL at
INFO -- which put the live key in the container log on the first production committee run.
"""
from __future__ import annotations

import logging

from app import logging_config


def test_httpx_request_urls_are_not_logged_at_info(caplog):
    logging_config.quiet_http_clients()
    caplog.set_level(logging.INFO)
    logging.getLogger("httpx").info('HTTP Request: POST https://example.test/v1/m:generate?key=SECRETKEY123 "HTTP/1.1 200 OK"')
    assert "SECRETKEY123" not in caplog.text


def test_httpx_failures_still_surface(caplog):
    logging_config.quiet_http_clients()
    caplog.set_level(logging.INFO)
    logging.getLogger("httpx").warning("connection problem")
    assert "connection problem" in caplog.text
