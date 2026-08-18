# Backend container for Cloud Run (or any container host).
#
# Firebase Hosting is static-only, so the API runs here and Hosting rewrites
# /api/** to it. That keeps the app and the API on ONE origin, which is what
# allows the refresh token to stay in a SameSite=Lax cookie.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build tooling is only needed while wheels are installed, so it is dropped
# from the final image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY alembic.ini ./
COPY app ./app
COPY scripts ./scripts

# Never run as root.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

# Cloud Run injects PORT; 8080 is its default.
ENV PORT=8080
EXPOSE 8080

# Single worker per container: scale with instances, not threads, so the
# database connection pool stays predictable.
CMD exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips '*'
