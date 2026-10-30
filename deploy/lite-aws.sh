#!/usr/bin/env bash
# =============================================================================
# lite-aws.sh — the $5 Lightsail option, wrapped.
#
#   bash deploy/lite-aws.sh up        terraform init + plan + apply
#   bash deploy/lite-aws.sh plan      terraform init + plan only
#   bash deploy/lite-aws.sh status    instance state + whether cloud-init finished
#   bash deploy/lite-aws.sh ip        print the static IP and the app URL
#   bash deploy/lite-aws.sh logs      tail /var/log/lite-boot.log (over SSH)
#   bash deploy/lite-aws.sh ssh       open a shell on the instance
#   bash deploy/lite-aws.sh snapshot  snapshot the instance before a teardown
#   bash deploy/lite-aws.sh down      terraform destroy (DESTRUCTIVE, asks)
#
# Everything below is Terraform in lite-infra/ plus AWS CLI reads. No application
# code is touched.
#
# ENVIRONMENT (optional):
#   TF_DIR       terraform directory        (default: lite-infra)
#   INSTANCE     lightsail instance name    (default: odoo-invoice-agent-lite-lite)
#   SSH_KEY      private key path           (default: lite-infra/lite-infra-key.pem)
#   FORCE=1      skip the typed confirmation in `down`
# =============================================================================
set -euo pipefail

TF_DIR="${TF_DIR:-lite-infra}"
INSTANCE="${INSTANCE:-odoo-invoice-agent-lite-lite}"
SSH_KEY="${SSH_KEY:-lite-infra/lite-infra-key.pem}"
AWS_REGION="${AWS_REGION:-eu-north-1}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# SSH_KEY defaults to a repo-relative path, but the script may be called from
# anywhere (e.g. from inside lite-infra/). Anchor it to the repo root unless the
# caller passed an absolute path.
case "$SSH_KEY" in
  /*|[A-Za-z]:[\\/]*) ;;
  *) SSH_KEY="${REPO_ROOT}/${SSH_KEY}" ;;
esac

say()  { printf '\033[1m>> %s\033[0m\n' "$*"; }
ok()   { printf '\033[32m   ok\033[0m %s\n' "$*"; }
warn() { printf '\033[33m   !! %s\033[0m\n' "$*"; }
die()  { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# `terraform` and `aws` are Windows executables on this kind of machine; WSL
# resolves them only when the .exe spelling is used, exactly like kubectl in
# deploy/local-k8s.sh.
resolve_exe() {
  case "$1" in
    */*) printf '%s' "$1" ;;
    *)
      if command -v "$1" >/dev/null 2>&1; then printf '%s' "$1"
      elif command -v "${1}.exe" >/dev/null 2>&1; then printf '%s' "${1}.exe"
      else printf '%s' "$1"
      fi ;;
  esac
}

TERRAFORM="$(resolve_exe "${TERRAFORM:-terraform}")"
AWS="$(resolve_exe "${AWS:-aws}")"

require() {
  if command -v "$1" >/dev/null 2>&1 || command -v "${1}.exe" >/dev/null 2>&1; then
    return 0
  fi
  die "$1 not found on PATH (required for '$2').
  Windows: run this from a shell where $1.exe is available, or use Terraform
  directly - the README shows the raw commands as well."
}

tf() { ( cd "${REPO_ROOT}/${TF_DIR}" && "$TERRAFORM" "$@" ); }

# Read one output value from the state, without needing credentials.
tf_output() { tf output -raw "$1" 2>/dev/null; }

# --- commands ---------------------------------------------------------------
cmd_up() {
  require "$TERRAFORM" "up"
  say "terraform init"
  tf init -input=false
  say "terraform plan"
  tf plan -input=false -out=lite.tfplan
  say "terraform apply"
  tf apply -input=false lite.tfplan
  rm -f "${REPO_ROOT}/${TF_DIR}/lite.tfplan"
  echo
  ok "applied"
  cmd_ip
  echo
  echo "   First boot installs Docker and then builds the image: 30-60 minutes."
  echo "   Watch it with:  bash deploy/lite-aws.sh logs"
}

cmd_plan() {
  require "$TERRAFORM" "plan"
  tf init -input=false
  tf plan -input=false
}

cmd_ip() {
  local ip
  ip="$(tf_output static_ip || true)"
  if [ -z "$ip" ]; then
    warn "no static_ip in state - has 'terraform apply' run?"
    return 1
  fi
  echo "   url:  http://${ip}/web/login"
  echo "   ssh:  ssh -i ${SSH_KEY} ubuntu@${ip}"
}

cmd_status() {
  require "$AWS" "status"
  say "lightsail instance"
  "$AWS" lightsail get-instance --region "$AWS_REGION" \
    --instance-name "$INSTANCE" \
    --query 'instance.{name:name,state:state.name,ip:publicIpAddress,blueprint:blueprintId,bundle:bundleId}' \
    --output table 2>/dev/null || warn "instance '$INSTANCE' not found in $AWS_REGION"

  say "cloud-init (last lines of /var/log/lite-boot.log)"
  if [ -f "$SSH_KEY" ]; then
    local ip; ip="$(tf_output static_ip || true)"
    if [ -n "$ip" ]; then
      ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
        "ubuntu@${ip}" 'sudo tail -n 15 /var/log/lite-boot.log 2>/dev/null || echo "(no boot log yet)"' \
        || warn "ssh failed - the instance may still be booting"
    fi
  else
    warn "no SSH key at $SSH_KEY (see: terraform output -raw ssh_private_key)"
  fi
}

cmd_logs() {
  require "$AWS" "logs"
  local ip; ip="$(tf_output static_ip || true)"
  [ -n "$ip" ] || die "no static_ip in state"
  [ -f "$SSH_KEY" ] || die "no SSH key at $SSH_KEY. Create it with:
  (cd $TF_DIR && terraform output -raw ssh_private_key > lite-infra-key.pem) && chmod 600 $SSH_KEY"
  say "following /var/log/lite-boot.log on ${ip} (Ctrl-C to stop)"
  ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new \
    "ubuntu@${ip}" 'sudo tail -f /var/log/lite-boot.log'
}

cmd_ssh() {
  local ip; ip="$(tf_output static_ip || true)"
  [ -n "$ip" ] || die "no static_ip in state"
  [ -f "$SSH_KEY" ] || die "no SSH key at $SSH_KEY"
  exec ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "ubuntu@${ip}"
}

cmd_snapshot() {
  require "$AWS" "snapshot"
  local name; name="manual-$(date +%Y%m%d-%H%M%S)"
  say "snapshotting ${INSTANCE} as ${name}"
  "$AWS" lightsail create-instance-snapshot --region "$AWS_REGION" \
    --instance-name "$INSTANCE" --instance-snapshot-name "$name"
  ok "snapshot ${name} created (billed per GB-month)"
}

cmd_down() {
  require "$TERRAFORM" "down"
  echo "terraform destroy deletes the instance AND its disk: the Odoo database"
  echo "and filestore are gone. There is no undo."
  echo
  echo "   Take a snapshot first:  bash deploy/lite-aws.sh snapshot"
  echo
  if [ "${FORCE:-0}" != "1" ]; then
    printf "Type 'yes' to destroy: "
    read -r answer
    [ "$answer" = "yes" ] || { echo "aborted."; exit 1; }
  fi
  tf destroy -input=false -auto-approve
  ok "destroyed"
}

cmd_help() { sed -n '2,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

case "${1:-help}" in
  up)       cmd_up ;;
  plan)     cmd_plan ;;
  status)   cmd_status ;;
  ip)       cmd_ip ;;
  logs)     cmd_logs ;;
  ssh)      cmd_ssh ;;
  snapshot) cmd_snapshot ;;
  down)     cmd_down ;;
  help|-h|--help) cmd_help ;;
  *)        die "unknown command '$1' (try: bash deploy/lite-aws.sh help)" ;;
esac
