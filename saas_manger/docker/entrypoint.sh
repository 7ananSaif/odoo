#!/bin/sh
# =============================================================================
# entrypoint.sh — container entrypoint for the SaaS Manager services.
#
# Runs on every start of saas-manager-web / -worker / -beat:
#   1. waits until the PostgreSQL server accepts connections;
#   2. (SAAS_CREATE_DB=1, web role) creates the manager database if missing;
#   3. (SAAS_DB_INIT=1, web role) creates/updates the schema and seeds defaults;
#   4. execs the service command passed as CMD (uvicorn / celery worker / beat).
#
# Everything is driven by the environment, so the same image runs every role.
# The database work is idempotent: re-running the containers is always safe.
# =============================================================================
set -eu

log() { printf '[saas-manager] %s\n' "$*"; }

if [ -n "${MANAGER_DB_URL:-}" ]; then
    log "waiting for the database host to accept connections"
    python - <<'PY'
import os
import sys
import time

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url

url = make_url(os.environ["MANAGER_DB_URL"])
host = url.host or "localhost"
port = url.port or 5432
user = url.username
password = url.password
name = url.database


def connect(dbname):
    return psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
        connect_timeout=5,
    )


# 1. Wait for the server (up to ~2 minutes). `template1` always exists, so it
#    works as the maintenance connection even before the manager DB is created.
for attempt in range(1, 61):
    try:
        connect("template1").close()
        print("[saas-manager] database is up")
        break
    except Exception as exc:  # noqa: BLE001
        print(f"[saas-manager] waiting for database ({attempt}/60): {exc}")
        time.sleep(2)
else:
    sys.exit("[saas-manager] database never became reachable")

# 2. Create the manager database on first boot (web role only).
if os.environ.get("SAAS_CREATE_DB", "0") == "1":
    conn = connect("template1")
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
        if cur.fetchone():
            print(f"[saas-manager] database {name!r} already exists")
        else:
            cur.execute(
                sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0").format(
                    sql.Identifier(name)
                )
            )
            print(f"[saas-manager] created database {name!r}")
    conn.close()
PY
fi

if [ "${SAAS_DB_INIT:-0}" = "1" ]; then
    log "creating/updating the manager schema"
    python scripts/init_db.py
fi

exec "$@"
