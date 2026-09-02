from __future__ import annotations

import os
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .logging_config import request_id_var, setup_logging
from .routers import admin, auth, data, jobs_ws, monte_carlo, reports, ws

app = FastAPI(
    title="GlassBox API",
    description="FastAPI gateway over the multi-agent-trading-system engine.",
    version="0.1.0",
)

request_logger = setup_logging()

# CORS_ALLOWED_ORIGINS: comma-separated list, e.g.
# "http://localhost:3000,https://app.yourdomain.com". Defaults to the local
# dev origin only -- production deployments must set this explicitly
# (docker-compose.yml derives it from APP_DOMAIN) or browser-based logins
# from the deployed frontend are silently blocked by CORS while curl/direct
# API calls keep working, since CORS is enforced by the browser, not the API.
_cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_tracing_middleware(request: Request, call_next):
    """Assigns a request id, echoes it back as X-Request-ID, and logs one
    structured line per request. Deliberately logs no headers/bodies --
    see logging_config.py for why."""
    request_id = str(uuid.uuid4())
    token = request_id_var.set(request_id)
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        request_id_var.reset(token)
        raise
    request_id_var.reset(token)
    duration_ms = int((time.monotonic() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    request_logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "request_id": request_id,
        },
    )
    return response


app.include_router(data.router)
app.include_router(monte_carlo.router)
app.include_router(ws.router)
app.include_router(jobs_ws.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(reports.router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
