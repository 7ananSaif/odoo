#!/usr/bin/env bash
# =============================================================================
# local-k8s.sh — bring the Odoo stack up on Docker Desktop's Kubernetes or kind.
#
#   bash deploy/local-k8s.sh up        cluster + image (nothing applied yet)
#   bash deploy/local-k8s.sh deploy    apply manifests, wait, init schema, wait
#   bash deploy/local-k8s.sh down      stop workloads, KEEP volumes
#   bash deploy/local-k8s.sh destroy   delete the namespace + volumes (DESTRUCTIVE)
#   bash deploy/local-k8s.sh db-shell  psql in the Postgres pod
#   bash deploy/local-k8s.sh db-backup pg_dump -> $BACKUP_DIR
#   bash deploy/local-k8s.sh logs      follow Odoo logs
#   bash deploy/local-k8s.sh url       print the URL for this cluster type
#   bash deploy/local-k8s.sh status    pods / services / PVCs / job
#
# This script is the implementation behind k8s-local/Makefile, and is also the
# entry point for anyone who does not have GNU make installed (this machine did
# not). No application code is touched by any of it: it builds the repo's own
# image and applies the manifests in k8s-local/base.
#
# ENVIRONMENT (all optional, same names as the Makefile variables):
#   CLUSTER        docker-desktop | kind | none        (default: docker-desktop)
#   CLUSTER_NAME   kind cluster name                   (default: odoo-local)
#   NAMESPACE      Kubernetes namespace                (default: odoo-local)
#   IMAGE          image the manifests reference       (default: odoo-local:19)
#   BASE_IMAGE     repo image built first              (default: odoo-invoice-agent:local)
#   KUBECTL/DOCKER/KIND                            (defaults: the commands)
#   BACKUP_DIR     where db-backup writes              (default: backups)
#   SKIP_BUILD=1   do not rebuild the image in `up`
#   FORCE=1        skip the typed confirmation in `destroy`
#   TIMEOUT        per-wait timeout in seconds         (default: 600)
#
# REQUIRES: docker, kubectl, and (for CLUSTER=kind) kind. GNU bash.
# =============================================================================
set -euo pipefail

# --- make the CLI tools discoverable ----------------------------------------
# On Windows the Docker CLI and kubectl are installed under
# "%ProgramFiles%\Docker\Docker\resources\bin", and a Git-bash session does not
# always inherit that directory: PowerShell finds `kubectl`, bash then does not,
# and this script dies with "kubectl not found on PATH" even though the tool is
# installed and working. (Observed on the machine this was developed on.)
#
# Adding the known install directories to PATH - if they exist and are not
# already there - keeps every call in this file a plain `kubectl ...` instead of
# an absolute path that would then need quoting at ~20 call sites. On Linux and
# macOS none of these directories exist, so this is a no-op there.
for _tool_dir in \
  "/c/Program Files/Docker/Docker/resources/bin" \
  "/mnt/c/Program Files/Docker/Docker/resources/bin" \
  "${PROGRAMFILES:-/nonexistent}/Docker/Docker/resources/bin" \
  "${USERPROFILE:-/nonexistent}/bin" \
  "/mnt/c/Users/${USER:-nobody}/bin" \
  "${HOME:-/nonexistent}/.local/bin" ; do
  if [ -d "$_tool_dir" ]; then
    case ":${PATH}:" in
      *":${_tool_dir}:"*) ;;
      *) PATH="${_tool_dir}:${PATH}" ;;
    esac
  fi
done
export PATH
unset _tool_dir

# The Windows executables are not all named the same way on an interop PATH:
# Docker ships BOTH `docker` and `docker.exe`, but kubectl ships ONLY
# `kubectl.exe`. Bash resolves `docker` happily and then cannot find `kubectl`
# at all - even though the same directory is on PATH and PowerShell runs it.
# So each tool name is resolved once, here, to whichever spelling actually
# exists; call sites keep using `$KUBECTL ...` and need no .exe knowledge.
resolve_exe() {
  case "$1" in
    */*) printf '%s' "$1" ;;                                   # an explicit path: leave it alone
    *)
      if command -v "$1" >/dev/null 2>&1; then printf '%s' "$1"
      elif command -v "${1}.exe" >/dev/null 2>&1; then printf '%s' "${1}.exe"
      else printf '%s' "$1"                                    # unresolvable: let require() explain
      fi ;;
  esac
}

CLUSTER="${CLUSTER:-docker-desktop}"
CLUSTER_NAME="${CLUSTER_NAME:-odoo-local}"
NAMESPACE="${NAMESPACE:-odoo-local}"
IMAGE="${IMAGE:-odoo-local:19}"
BASE_IMAGE="${BASE_IMAGE:-odoo-invoice-agent:local}"
KUBECTL="$(resolve_exe "${KUBECTL:-kubectl}")"
DOCKER="$(resolve_exe "${DOCKER:-docker}")"
KIND="$(resolve_exe "${KIND:-kind}")"
BACKUP_DIR="${BACKUP_DIR:-backups}"
TIMEOUT="${TIMEOUT:-600}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Windows path interop ----------------------------------------------------
# When bash is WSL and kubectl/docker are Windows executables (see resolve_exe
# above), the tools do NOT understand WSL paths: passing
# /mnt/d/odoo/odoo/k8s-local/base makes kubectl look for D:\mnt\d\odoo\...
#   error: must build at directory: not a valid directory:
#   evalsymlink failure on '/mnt/d/odoo/odoo/k8s-local/base'
# The fix is to never hand those tools an absolute WSL path. Everything that
# takes a path is run from the repo root with a path RELATIVE to it, which both
# WSL and Windows binaries resolve correctly. On Linux/macOS this is simply the
# working directory and changes nothing.
MANIFESTS_REL="k8s-local/base"
KIND_CONFIG_REL="k8s-local/kind-cluster.yaml"

# Run a command from the repo root. Used for every tool invocation that takes a
# filesystem path (-k DIR, -f FILE, build CONTEXT, cluster --config).
in_repo() { ( cd "$REPO_ROOT" && "$@" ); }

# --- output helpers ----------------------------------------------------------
say()  { printf '\033[1m>> %s\033[0m\n' "$*"; }
ok()   { printf '\033[32m   ok\033[0m %s\n' "$*"; }
warn() { printf '\033[33m   !! %s\033[0m\n' "$*"; }
die()  { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

require() {
  # Second chance for the Windows convention, where the executable on PATH is
  # `kubectl.exe` while the script (and every document in this repo) says
  # `kubectl`. Harmless on other platforms.
  if command -v "$1" >/dev/null 2>&1 || command -v "${1}.exe" >/dev/null 2>&1; then
    return 0
  fi
  die "$1 not found on PATH (required for '$2').
  Install it, or pass its path, e.g.:  KUBECTL=/path/to/kubectl bash $0 $2"
}

# --- cluster selection -------------------------------------------------------
use_context() {
  local ctx="$1"
  if $KUBECTL config get-contexts -o name | grep -qx "$ctx"; then
    $KUBECTL config use-context "$ctx" >/dev/null
    ok "kubectl context: $ctx"
  else
    return 1
  fi
}

select_cluster() {
  case "$CLUSTER" in
    docker-desktop)
      require "$KUBECTL" "cluster access"
      use_context docker-desktop || die "no 'docker-desktop' context.
  Enable it: Docker Desktop > Settings > Kubernetes > Enable Kubernetes.
  Or run with CLUSTER=kind (creates its own cluster)."
      $KUBECTL cluster-info >/dev/null 2>&1 || die "context 'docker-desktop' exists but the API server is unreachable.
  Is Kubernetes started in Docker Desktop?"
      ;;
    kind)
      require "$KUBECTL" "cluster access"
      require "$KIND" "kind cluster creation"
      if $KIND get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
        ok "kind cluster '$CLUSTER_NAME' already exists"
      else
        say "creating kind cluster '$CLUSTER_NAME' (1-2 min)"
        in_repo "$KIND" create cluster --config "$KIND_CONFIG_REL"
      fi
      use_context "kind-${CLUSTER_NAME}" || die "kind created '${CLUSTER_NAME}' but context 'kind-${CLUSTER_NAME}' is missing"
      ;;
    none)
      require "$KUBECTL" "cluster access"
      ok "using the current context: $($KUBECTL config current-context)"
      ;;
    *)
      die "unknown CLUSTER='$CLUSTER' (expected: docker-desktop | kind | none)"
      ;;
  esac
}

# --- image ------------------------------------------------------------------
build_image() {
  require "$DOCKER" "image build"
  if [ "${SKIP_BUILD:-0}" = "1" ]; then
    warn "SKIP_BUILD=1 - not rebuilding ${IMAGE}"
    return
  fi

  # The base layer comes from the repo's own Dockerfile: odoo:19 + tesseract +
  # the addon's requirements.txt. It is the slow build (apt + pip) and it is the
  # real production image, so the cluster runs what production runs.
  if ! $DOCKER image inspect "$BASE_IMAGE" >/dev/null 2>&1; then
    say "building ${BASE_IMAGE} from ./Dockerfile (first run: apt + pip, 5-15 min)"
    in_repo "$DOCKER" build -t "$BASE_IMAGE" .
  else
    ok "base image ${BASE_IMAGE} already present (rebuild: docker build -t ${BASE_IMAGE} .)"
  fi

  # Thin layer: bakes custom_addons into /mnt/extra-addons, which compose
  # bind-mounted and a cluster cannot.
  say "building ${IMAGE} (addons layer)"
  in_repo "$DOCKER" build -f k8s-local/Dockerfile.app -t "$IMAGE" \
    --build-arg "BASE_IMAGE=${BASE_IMAGE}" .
  ok "image ready: ${IMAGE}"
}

load_image() {
  # Docker Desktop shares its image store with its Kubernetes node, so nothing
  # to do. A kind node runs its own containerd: the image must be pushed into it
  # or the pod fails with ErrImageNeverPull / ErrImagePull.
  case "$CLUSTER" in
    kind)
      require "$KIND" "image load"
      say "loading ${IMAGE} into kind node(s)"
      $KIND load docker-image "$IMAGE" --name "$CLUSTER_NAME"
      ok "image loaded into kind"
      ;;
    *)
      ok "cluster shares the local image store (no load needed)"
      ;;
  esac
}

# --- deploy -----------------------------------------------------------------
cmd_up() {
  require "$KUBECTL" "cluster access"
  select_cluster
  build_image
  load_image
  say "cluster is ready. Next: bash deploy/local-k8s.sh deploy"
}

cmd_deploy() {
  require "$KUBECTL" "deploy"
  [ -d "${REPO_ROOT}/${MANIFESTS_REL}" ] || die "manifests not found at ${REPO_ROOT}/${MANIFESTS_REL}"

  select_cluster

  # The init Job is immutable once complete, so a re-deploy must remove it
  # before `apply` can recreate it. Do it before the apply, not after, or the
  # first apply fails with "field is immutable".
  $KUBECTL delete job odoo-init -n "$NAMESPACE" --ignore-not-found >/dev/null 2>&1 || true

  say "applying manifests from ${MANIFESTS_REL}"
  in_repo "$KUBECTL" apply -k "$MANIFESTS_REL"

  say "waiting for postgres to become ready (up to ${TIMEOUT}s)"
  $KUBECTL rollout status statefulset/postgres -n "$NAMESPACE" --timeout="${TIMEOUT}s" \
    || die "postgres did not become ready. Check: kubectl logs -n $NAMESPACE statefulset/postgres --previous"

  # The schema init. Until this completes, Odoo is Running but not Ready: its
  # readiness probe is the DB-aware health route, which 500s on an empty
  # database (see k8s-local/base/07-odoo-deployment.yaml).
  say "initialising the odoo database schema (--init=base, up to ${TIMEOUT}s)"
  $KUBECTL wait --for=condition=complete "job/odoo-init" -n "$NAMESPACE" --timeout="${TIMEOUT}s" \
    || {
      $KUBECTL logs -n "$NAMESPACE" job/odoo-init --tail=80 || true
      die "schema init failed. Logs above. Re-run: bash deploy/local-k8s.sh deploy"
    }
  ok "database schema initialised"

  say "waiting for the Odoo rollout (up to ${TIMEOUT}s)"
  $KUBECTL rollout status deployment/odoo -n "$NAMESPACE" --timeout="${TIMEOUT}s" \
    || die "odoo did not become ready. Check: kubectl logs -n $NAMESPACE deployment/odoo"

  echo
  ok "deployed"
  cmd_url
  $KUBECTL get pods,svc -n "$NAMESPACE"
}

cmd_down() {
  require "$KUBECTL" "scale down"
  say "stopping workloads (volumes are NOT touched)"
  $KUBECTL scale deployment/odoo    -n "$NAMESPACE" --replicas=0 2>/dev/null || warn "no odoo deployment"
  $KUBECTL scale statefulset/postgres -n "$NAMESPACE" --replicas=0 2>/dev/null || warn "no postgres statefulset"
  echo
  say "persistent volume claims kept:"
  $KUBECTL get pvc -n "$NAMESPACE" || true
  echo
  echo "   data preserved. resume:  bash deploy/local-k8s.sh deploy"
  echo "   delete data:            bash deploy/local-k8s.sh destroy   (DESTRUCTIVE)"
}

cmd_destroy() {
  require "$KUBECTL" "teardown"
  echo "This deletes namespace '${NAMESPACE}': the Odoo DATABASE and the FILESTORE."
  echo "There is no undo."
  echo
  if [ "${FORCE:-0}" != "1" ]; then
    printf "Type 'yes' to continue: "
    read -r answer
    [ "$answer" = "yes" ] || { echo "aborted."; exit 1; }
  fi
  $KUBECTL delete namespace "$NAMESPACE" --ignore-not-found
  ok "namespace ${NAMESPACE} deleted"
  echo "PersistentVolumes with a Retain policy may survive; check: $KUBECTL get pv"
}

cmd_status() {
  require "$KUBECTL" "status"
  $KUBECTL get pods,svc,pvc,job -n "$NAMESPACE" -o wide
}

# --- database ---------------------------------------------------------------
cmd_db_shell() {
  require "$KUBECTL" "db-shell"
  # PGPASSWORD comes from the container's own POSTGRES_PASSWORD env (set by the
  # Secret), so no credential is typed, echoed, or left in shell history.
  # `-it` needs a TTY: this target is interactive by design.
  $KUBECTL exec -it statefulset/postgres -n "$NAMESPACE" -- \
    sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
}

cmd_db_backup() {
  require "$KUBECTL" "db-backup"
  mkdir -p "$BACKUP_DIR"
  local stamp target
  stamp="$(date +%Y%m%d-%H%M%S)"
  target="${BACKUP_DIR}/odoo-${stamp}.dump"

  say "pg_dump -Fc inside postgres-0"
  # Custom format (-Fc) because that is what pg_restore expects and what
  # scripts/db-migrate.sh already uses for the RDS migration path.
  $KUBECTL exec -n "$NAMESPACE" statefulset/postgres -- \
    sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -Fc --no-owner -d "$POSTGRES_DB" -f /tmp/odoo.dump'

  say "copying the dump out to ${target}"
  # kubectl cp takes a LOCAL path on the right-hand side, so it is subject to
  # the same Windows-path interop rule: run it from the repo root.
  in_repo "$KUBECTL" cp "${NAMESPACE}/postgres-0:/tmp/odoo.dump" "$target"
  $KUBECTL exec -n "$NAMESPACE" statefulset/postgres -- rm -f /tmp/odoo.dump

  [ -s "$target" ] || die "backup file is empty: $target"
  ok "backup written: $(du -h "$target" | cut -f1)  ${target}"
  echo
  echo "Restore it with:"
  echo "  kubectl cp ${target} ${NAMESPACE}/postgres-0:/tmp/restore.dump"
  echo "  kubectl exec -n ${NAMESPACE} statefulset/postgres -- \\"
  echo "    sh -c 'PGPASSWORD=\$POSTGRES_PASSWORD pg_restore -U \$POSTGRES_USER -d \$POSTGRES_DB --clean --if-exists --no-owner /tmp/restore.dump'"
}

# --- logs / url -------------------------------------------------------------
cmd_logs() {
  require "$KUBECTL" "logs"
  $KUBECTL logs -n "$NAMESPACE" deployment/odoo -f --tail=200
}

cmd_url() {
  case "$CLUSTER" in
    kind)
      echo "   http://localhost:8081   (kind: nodePort 30080 -> host 8081)"
      ;;
    *)
      echo "   http://localhost:30080  (Docker Desktop publishes NodePorts)"
      ;;
  esac
  echo "   kubectl port-forward -n ${NAMESPACE} svc/odoo 8069:8069  ->  http://localhost:8069"
}

cmd_help() {
  sed -n '2,32p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

case "${1:-help}" in
  up)        cmd_up ;;
  deploy)    cmd_deploy ;;
  down)      cmd_down ;;
  destroy)   cmd_destroy ;;
  status)    cmd_status ;;
  db-shell)  cmd_db_shell ;;
  db-backup) cmd_db_backup ;;
  logs)      cmd_logs ;;
  url)       cmd_url ;;
  help|-h|--help) cmd_help ;;
  *)         die "unknown command '$1' (try: bash deploy/local-k8s.sh help)" ;;
esac
