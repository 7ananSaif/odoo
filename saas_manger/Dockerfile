# =============================================================================
# Dockerfile — SaaS Manager (FastAPI + Celery) image for the Odoo Compose stack
#
# One image, three roles (see ../docker-compose.yml):
#   * saas-manager-web    → uvicorn app.main:app on :8080
#   * saas-manager-worker → celery worker (queues: default, updates, backups)
#   * saas-manager-beat   → celery beat scheduler
#
# Multi-stage so the runtime image carries only the app, its dependencies and
# the PostgreSQL client tools the manager shells out to for backups.
#
# The image is built with context ./saas_manger, so paths below are relative to
# the saas_manger/ directory.
# =============================================================================

# --- Stage 1: builder — compile dependency wheels ---------------------------
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# argon2-cffi and psycopg2-binary need a compiler for their sdist fallback.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# --- Stage 2: runtime --------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# postgresql-client provides pg_dump / pg_restore / psql. The manager's backup
# service runs them as configured by PG_DUMP / PG_RESTORE / PG_PSQL, against
# the compose `db` service over the private network.
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the application dependencies from the prebuilt wheels, then drop the
# wheels — nothing else is needed at runtime.
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Application source, templates/static and the helper scripts the entrypoint
# and the operator run (scripts/init_db.py, scripts/create_owner.py).
COPY app ./app
COPY scripts ./scripts
COPY pyproject.toml README.md ./

# Entrypoint: waits for Postgres, optionally creates the manager database +
# schema, then execs the service command passed as CMD.
COPY docker/entrypoint.sh /usr/local/bin/saas-entrypoint.sh
RUN chmod +x /usr/local/bin/saas-entrypoint.sh

# Non-root runtime user; owns the app and the backup directory.
RUN groupadd -g 10001 saas \
    && useradd -u 10001 -g saas -m -s /usr/sbin/nologin saas \
    && mkdir -p /app/backups /app/logs \
    && chown -R saas:saas /app

USER saas

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/saas-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
