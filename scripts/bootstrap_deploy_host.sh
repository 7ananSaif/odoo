#!/usr/bin/env bash
# =============================================================================
# scripts/bootstrap_deploy_host.sh — one-time preparation of an EC2 host so
# the GitHub Actions deploy pipeline (.github/workflows/deploy.yml) can drive
# it over SSH.
#
# WHAT IT SETS UP
#   1. Docker Engine + Compose v2 CLI plugin (docker compose ...)
#   2. Git checkout of the production branch at /opt/odoo (deploy's CWD)
#   3. /opt/odoo/backups dir (pre-deploy DB snapshots land here)
#   4. Sanity checks the pipeline implicitly relies on (flock, ghcr auth hint)
#
# RUN THIS ON THE TARGET INSTANCE as your deploy user (e.g. ubuntu):
#   REPO_URL=https://github.com/7ananSaif/odoo.git bash bootstrap_deploy_host.sh
#
# AFTER THIS
#   - Put your .env at /opt/odoo/.env (DOMAIN=..., POSTGRES_..., ANTHROPIC_API_KEY...)
#     — the deploy refuses to run without DOMAIN set in it.
#   - Update the GitHub repo secrets: EC2_HOST, EC2_USERNAME, SSH_PRIVATE_KEY.
# =============================================================================

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/7ananSaif/odoo.git}"
BRANCH="${BRANCH:-production}"
TARGET_DIR="/opt/odoo"

echo "=== Bootstrap deploy host: $(hostname) ($(date)) ==="

# -----------------------------------------------------------------------------
# 1. Docker Engine + Compose v2
# -----------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    echo "--- Installing Docker Engine ---"
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
    echo "docker already installed: $(docker --version)"
fi

# Compose v2 plugin check ("docker compose" subcommand form)
if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: 'docker compose' v2 plugin not available after install." >&2
    exit 1
fi
echo "docker compose OK: $(docker compose version)"

# Deploy runs plain `docker`/`docker compose` over SSH without sudo — the
# deploy user must be in the docker group. Takes effect on next login.
if ! id -nG "$USER" | grep -qw docker; then
    echo "--- Adding $USER to docker group (re-login required) ---"
    sudo usermod -aG docker "$USER"
fi

# flock is used by the deploy single-instance guard (/opt/odoo/deploy.lock)
if ! command -v flock >/dev/null 2>&1; then
    sudo apt-get install -y util-linux
fi

# -----------------------------------------------------------------------------
# 2. Repo checkout at /opt/odoo (the deploy cd's here)
# -----------------------------------------------------------------------------
if [ ! -d "$TARGET_DIR/.git" ]; then
    echo "--- Cloning $REPO_URL ($BRANCH) -> $TARGET_DIR ---"
    sudo mkdir -p "$TARGET_DIR"
    sudo chown "$USER":"$USER" "$TARGET_DIR"
    git clone --branch "$BRANCH" "$REPO_URL" "$TARGET_DIR"
else
    echo "$TARGET_DIR already has a git checkout — skipping clone"
fi

mkdir -p "$TARGET_DIR/backups"

# -----------------------------------------------------------------------------
# 3. .env presence check (deploy hard-fails without DOMAIN in it)
# -----------------------------------------------------------------------------
if [ ! -f "$TARGET_DIR/.env" ]; then
    cat <<EOF

ACTION REQUIRED: no $TARGET_DIR/.env found.
Copy your environment file to $TARGET_DIR/.env — it must contain at least:
    DOMAIN=<your-domain>
plus POSTGRES_*, RABBITMQ_*, ANTHROPIC_API_KEY, URL, REDIS_URL, ...
The deploy pipeline exits early without it.

EOF
else
    echo ".env present"
fi

# -----------------------------------------------------------------------------
# 4. ghcr.io auth hint (invoice-ai images come from a private GHCR package)
# -----------------------------------------------------------------------------
if ! grep -q "ghcr.io" ~/.docker/config.json 2>/dev/null; then
    cat <<'EOF'

NOTE: invoice-ai deploys pull ghcr.io/7anansaif/invoice-ai. If that package
is private, authenticate once on this host:
    echo <GHCR_TOKEN> | docker login ghcr.io -u <USERNAME> --password-stdin

EOF
fi

echo ""
echo "=== Bootstrap complete ==="
echo "Next steps:"
echo "  1. Ensure $TARGET_DIR/.env exists with DOMAIN set"
echo "  2. Log out/in once so the docker group applies"
echo "  3. Update GitHub secrets: EC2_HOST, EC2_USERNAME, SSH_PRIVATE_KEY"
echo "  4. Point DNS (e.g. cloud-ai-erp.duckdns.org) at this host's IP"
echo "  5. Re-run the deploy workflow"
