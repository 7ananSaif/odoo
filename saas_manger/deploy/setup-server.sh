#!/usr/bin/env bash
# =============================================================================
# setup-server.sh — one-time bootstrap of the SaaS Manager on an Ubuntu/Debian
# (or Amazon Linux) host. Run it ONCE, on the EC2 instance, from inside a clone
# of this repository:
#
#     git clone <repo-url> /opt/saas_manger
#     cd /opt/saas_manger
#     bash deploy/setup-server.sh
#
# It installs the system packages (git, python, nginx, redis), creates the
# virtualenv, installs the three systemd units and the nginx site, and grants the
# deploy user permission to restart just those units. After this you edit .env
# and run `bash deploy/deploy.sh` (or push to main) to bring the app up.
#
# Environment overrides:
#     APP_USER      OS user that runs the services   (default: current user)
#     SERVER_NAME   nginx server_name                (default: _ = catch-all)
#     APP_DIR       install directory                (default: repo root)
# =============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${APP_DIR:-$REPO_DIR}"
APP_USER="${APP_USER:-$(id -un)}"
SERVER_NAME="${SERVER_NAME:-_}"
BRANCH="${BRANCH:-main}"

SERVICES=(saas-manager-web saas-manager-worker saas-manager-beat)

log()  { printf '\033[1;34m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[setup]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[setup]\033[0m %s\n' "$*" >&2; exit 1; }

# Root or passwordless sudo.
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

log "Repository : $REPO_DIR"
log "Install dir: $APP_DIR"
log "Run as user: $APP_USER"
log "Server name: $SERVER_NAME"

[ -f "$REPO_DIR/deploy/deploy.sh" ] || die "$REPO_DIR does not look like the SaaS Manager repo."

# -----------------------------------------------------------------------------
# 1. System packages
# -----------------------------------------------------------------------------
log "Installing system packages"
if command -v apt-get >/dev/null 2>&1; then
  $SUDO apt-get update -y
  $SUDO apt-get install -y git python3 python3-venv python3-pip curl ca-certificates nginx
  # Redis: 'redis-server' on Debian/Ubuntu.
  $SUDO apt-get install -y redis-server || warn "redis-server not installed — install Redis manually."
elif command -v dnf >/dev/null 2>&1; then
  $SUDO dnf install -y git python3 python3-pip curl nginx
  # Amazon Linux 2023 ships Redis as 'redis6'; older yum as 'redis'.
  $SUDO dnf install -y redis6 || $SUDO dnf install -y redis || warn "Redis not installed — install it manually."
elif command -v yum >/dev/null 2>&1; then
  $SUDO yum install -y git python3 python3-pip curl nginx
  $SUDO amazon-linux-extras install -y redis6 2>/dev/null || \
    $SUDO yum install -y redis || warn "Redis not installed — install it manually."
else
  die "Unsupported package manager (no apt-get/dnf/yum). Install git, python3, nginx and redis manually, then re-run."
fi

# -----------------------------------------------------------------------------
# 2. Enable Redis
# -----------------------------------------------------------------------------
REDIS_UNIT=""
for candidate in redis-server redis6 redis; do
  if systemctl list-unit-files 2>/dev/null | grep -q "^${candidate}\.service"; then
    REDIS_UNIT="$candidate"
    break
  fi
done
if [ -n "$REDIS_UNIT" ]; then
  log "Enabling Redis ($REDIS_UNIT)"
  $SUDO systemctl enable --now "$REDIS_UNIT"
else
  warn "Could not find a Redis systemd unit. Ensure Redis is running on $REPO_DIR .env CELERY_BROKER_URL."
fi

# -----------------------------------------------------------------------------
# 3. Directories + virtualenv + dependencies
# -----------------------------------------------------------------------------
log "Preparing directories and virtualenv"
$SUDO mkdir -p "$APP_DIR/logs" "$APP_DIR/backups"
$SUDO chown -R "$APP_USER":"$APP_USER" "$APP_DIR/logs" "$APP_DIR/backups"

if [ ! -d "$APP_DIR/venv" ]; then
  python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install --upgrade pip >/dev/null
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# -----------------------------------------------------------------------------
# 4. systemd units (substitute user + directory into the templates)
# -----------------------------------------------------------------------------
log "Installing systemd units"
for unit in "${SERVICES[@]}"; do
  src="$REPO_DIR/deploy/systemd/${unit}.service"
  [ -f "$src" ] || die "Missing unit template: $src"
  sed -e "s|__APP_USER__|$APP_USER|g" \
      -e "s|__APP_DIR__|$APP_DIR|g" \
      "$src" | $SUDO tee "/etc/systemd/system/${unit}.service" >/dev/null
  log "  installed /etc/systemd/system/${unit}.service"
done

$SUDO systemctl daemon-reload
for unit in "${SERVICES[@]}"; do
  $SUDO systemctl enable "$unit" >/dev/null 2>&1 || true
done

# -----------------------------------------------------------------------------
# 5. Allow the deploy user to restart just these units (for CI over SSH)
# -----------------------------------------------------------------------------
log "Granting '$APP_USER' passwordless restart of the SaaS Manager units"
SYSTEMCTL="$(command -v systemctl || echo /usr/bin/systemctl)"
SUDOERS_FILE="/etc/sudoers.d/saas-manager"
printf '%s\n' \
"# Managed by deploy/setup-server.sh — lets the deploy user restart the app units." \
"${APP_USER} ALL=(root) NOPASSWD: ${SYSTEMCTL} restart saas-manager-*, ${SYSTEMCTL} start saas-manager-*, ${SYSTEMCTL} stop saas-manager-*, ${SYSTEMCTL} is-active saas-manager-*" \
  | $SUDO tee "$SUDOERS_FILE" >/dev/null
$SUDO chmod 440 "$SUDOERS_FILE"
if ! $SUDO visudo -cf "$SUDOERS_FILE"; then
  $SUDO rm -f "$SUDOERS_FILE"
  die "Generated sudoers file failed validation and was removed."
fi

# -----------------------------------------------------------------------------
# 6. nginx reverse proxy
# -----------------------------------------------------------------------------
log "Installing nginx site"
NGINX_RENDERED="$(mktemp)"
sed -e "s|__APP_DIR__|$APP_DIR|g" \
    -e "s|__SERVER_NAME__|$SERVER_NAME|g" \
    "$REPO_DIR/deploy/nginx/saas-manager.conf" > "$NGINX_RENDERED"

if [ -d /etc/nginx/sites-available ]; then
  $SUDO cp "$NGINX_RENDERED" /etc/nginx/sites-available/saas-manager.conf
  $SUDO ln -sf /etc/nginx/sites-available/saas-manager.conf /etc/nginx/sites-enabled/saas-manager.conf
  # Drop the stock default site so it cannot shadow ours.
  [ -e /etc/nginx/sites-enabled/default ] && $SUDO rm -f /etc/nginx/sites-enabled/default
else
  $SUDO cp "$NGINX_RENDERED" /etc/nginx/conf.d/saas-manager.conf
fi
rm -f "$NGINX_RENDERED"

if $SUDO nginx -t; then
  $SUDO systemctl enable --now nginx
  $SUDO systemctl reload nginx 2>/dev/null || $SUDO systemctl restart nginx
else
  warn "nginx config test failed — fix /etc/nginx/.../saas-manager.conf and reload nginx."
fi

# -----------------------------------------------------------------------------
# 7. .env
# -----------------------------------------------------------------------------
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  warn "Created $APP_DIR/.env from .env.example — edit it and fill in the real values."
fi

# -----------------------------------------------------------------------------
# Done
# -----------------------------------------------------------------------------
cat <<EOF

$(printf '\033[1;32m[setup]\033[0m') Setup complete. Next steps on this host:

  1. Edit the environment file:
         nano $APP_DIR/.env          # SECRET_KEY, SECRETS_KEY, MANAGER_DB_URL, ODOO_*, PG_*, ...

  2. Create the manager database (if not already present):
         sudo -u postgres createdb saas_manager

  3. Create the schema + owner account:
         cd $APP_DIR
         ./venv/bin/python scripts/init_db.py
         ./venv/bin/python scripts/create_owner.py --email owner@example.com --name "Owner"

  4. Bring everything up (also what CI runs on every push):
         cd $APP_DIR && bash deploy/deploy.sh

  5. Verify:  curl -s http://127.0.0.1:8080/health

  Services: ${SERVICES[*]}
  Logs:     journalctl -u saas-manager-web -f
  Branch deployed by CI: $BRANCH

EOF
