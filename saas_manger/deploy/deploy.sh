#!/usr/bin/env bash
# =============================================================================
# deploy.sh — server-side deployment for the SaaS Manager.
#
# Run on the EC2 host (never on the developer machine). It:
#   1. pulls the latest code for $BRANCH from the git remote,
#   2. recreates/updates the virtualenv and installs requirements.txt,
#   3. ensures the manager database schema exists (idempotent),
#   4. restarts the three systemd services,
#   5. waits for the /health endpoint to come back green.
#
# It is idempotent and safe to run on every push. The GitHub Actions workflow
# `.github/workflows/deploy.yml` calls it over SSH; you can also run it by hand:
#
#     cd /opt/saas_manger
#     bash deploy/deploy.sh
#
# Environment overrides:
#     BRANCH            git branch to deploy            (default: main)
#     REMOTE            git remote name                 (default: origin)
#     VENV_DIR          virtualenv path                 (default: <repo>/venv)
#     HEALTH_URL        health probe URL                (default: http://127.0.0.1:8080/health)
#     HEALTH_RETRIES    probe attempts (2s apart)       (default: 15)
#     SKIP_PULL=1       skip the git pull (deploy current checkout)
# =============================================================================
set -euo pipefail

# --- Resolve locations -------------------------------------------------------
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Configuration -----------------------------------------------------------
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
VENV_DIR="${VENV_DIR:-$REPO_DIR/venv}"
SERVICES=(saas-manager-web saas-manager-worker saas-manager-beat)
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8080/health}"
HEALTH_RETRIES="${HEALTH_RETRIES:-15}"

# --- Helpers -----------------------------------------------------------------
log()  { printf '\033[1;34m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[deploy]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[deploy]\033[0m %s\n' "$*" >&2; exit 1; }

cd "$REPO_DIR"
log "Repository: $REPO_DIR"
log "Deploying branch '$BRANCH' from remote '$REMOTE'"

# --- Preconditions -----------------------------------------------------------
[ -f "$REPO_DIR/.env" ] || die \
"$REPO_DIR/.env is missing. Copy .env.example to .env and fill it in first (see deploy/README.md)."

# --- 1. Pull the latest code -------------------------------------------------
if [ "${SKIP_PULL:-0}" = "1" ]; then
  warn "SKIP_PULL=1 — deploying the current checkout without pulling."
else
  command -v git >/dev/null 2>&1 || die "git is not installed on the server."
  [ -d "$REPO_DIR/.git" ] || die \
    "$REPO_DIR is not a git working copy. Clone the repo first (see deploy/README.md)."

  log "Fetching $REMOTE/$BRANCH"
  git fetch --prune "$REMOTE"
  git checkout -B "$BRANCH" "$REMOTE/$BRANCH"
  git reset --hard "$REMOTE/$BRANCH"
  log "Now at $(git rev-parse --short HEAD) — $(git log -1 --pretty=%s)"
fi

# --- 2. Python environment ---------------------------------------------------
[ -d "$VENV_DIR" ] || { log "Creating virtualenv at $VENV_DIR"; python3 -m venv "$VENV_DIR"; }

log "Installing Python dependencies"
"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null
"$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt"

# --- 3. Manager database schema (idempotent) ---------------------------------
log "Ensuring manager database schema"
"$VENV_DIR/bin/python" scripts/init_db.py

# --- 4. Restart the services -------------------------------------------------
# Restarted one by one so the sudoers rule (see deploy/setup-server.sh) can match
# a single service name per call without a wildcard spanning spaces.
log "Restarting services: ${SERVICES[*]}"
for svc in "${SERVICES[@]}"; do
  if command -v sudo >/dev/null 2>&1; then
    sudo systemctl restart "$svc"
  else
    systemctl restart "$svc"
  fi
  log "  restarted $svc"
done

# --- 5. Health check ---------------------------------------------------------
log "Waiting for $HEALTH_URL"
for attempt in $(seq 1 "$HEALTH_RETRIES"); do
  if body="$(curl -fsS "$HEALTH_URL" 2>/dev/null)"; then
    log "Health check OK: $body"
    log "Deploy complete."
    exit 0
  fi
  sleep 2
done

die "Health check failed after $((HEALTH_RETRIES * 2))s.
Inspect the logs with:
    journalctl -u saas-manager-web -n 100 --no-pager
    journalctl -u saas-manager-worker -n 100 --no-pager
    journalctl -u saas-manager-beat -n 100 --no-pager"
