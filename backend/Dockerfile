# GlassBox backend — FastAPI gateway over the multi-agent-trading-system engine.
# Data artifacts (reports/, database/) are mounted at runtime from backend-source,
# NOT baked into this image — see docker-compose.yml volumes.

FROM python:3.12-slim AS base

WORKDIR /app

# System deps for pandas/pyarrow wheels on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY app ./app

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# 2 workers is a sane default for a single small VM; bump via WEB_CONCURRENCY.
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:8000 --access-logfile -"]
