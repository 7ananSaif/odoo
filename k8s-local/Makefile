# =============================================================================
# k8s-local/Makefile — the local Kubernetes option, one command per step.
#
#   make k8s-up       create/verify the cluster, build+load the image, apply base
#   make k8s-deploy   apply the manifests, wait for Postgres, init the schema,
#                     wait for the Odoo rollout, print the URL
#   make k8s-down     stop the workloads but KEEP the volumes (data survives)
#   make k8s-destroy  delete the namespace AND the volumes (DESTRUCTIVE)
#   make db-shell     psql inside the Postgres pod
#   make db-backup    pg_dump to ./backups/<timestamp>.dump (and verified)
#   make logs         follow the Odoo container logs
#
# WHY `.RECIPEPREFIX = >`
# -----------------------
# Make requires a literal TAB to start every recipe line. This file is edited by
# tools (editors, YAML/whitespace formatters, CI checkouts with autocrlf) that
# routinely turn those tabs into spaces, which breaks the file with the famously
# unhelpful "missing separator". Setting the recipe prefix to '>' makes the
# indentation explicit, visible in review, and immune to that class of damage.
# Requires GNU make >= 3.82 (2010). Check with `make --version`.
#
# WHY THE MULTI-STEP TARGETS CALL A SCRIPT
# ----------------------------------------
# `k8s-up` and `k8s-deploy` are sequences with real logic (cluster present? image
# loaded? is the init Job complete? did the rollout actually finish?). Expressing
# that inside recipe lines means shell-specific one-liners that differ between
# cmd.exe, PowerShell and bash. The logic lives in deploy/local-k8s.sh instead,
# where it is a normal, testable, line-by-line shell script - and the Makefile
# stays a readable index of operations. `make` needs a POSIX shell for those two
# targets (Git for Windows ships one; the repo's scripts/*.sh already assume it).
# db-shell / db-backup / logs are single kubectl calls and need no shell.
#
# Every variable can be overridden on the command line, e.g.
#   make k8s-up CLUSTER=kind
#   make k8s-deploy IMAGE=odoo-local:19
# =============================================================================

SHELL := /bin/bash

# --- cluster / naming --------------------------------------------------------
# CLUSTER selects which local Kubernetes `k8s-up` brings up:
#   docker-desktop (default) -> uses the context Docker Desktop installs
#   kind                     -> creates the kind cluster from ./kind-cluster.yaml
#   none                     -> use whatever context is current (you manage it)
CLUSTER        ?= docker-desktop
CLUSTER_NAME   ?= odoo-local
NAMESPACE      ?= odoo-local

# --- images ------------------------------------------------------------------
# BASE_IMAGE is built from the repo's own ./Dockerfile (the real app image).
# IMAGE adds custom_addons on top (see Dockerfile.app) and is what the cluster runs.
BASE_IMAGE     ?= odoo-invoice-agent:local
IMAGE          ?= odoo-local:19

# --- tooling -----------------------------------------------------------------
KUBECTL        ?= kubectl
DOCKER         ?= docker
KIND           ?= kind
DEPLOY_SCRIPT  ?= ../deploy/local-k8s.sh

# --- artifacts ---------------------------------------------------------------
# Backups land outside the manifests dir and are gitignored by the repo's
# `*.dump`-adjacent rules; see README "Backups".
BACKUP_DIR     ?= backups

.DEFAULT_GOAL  := help

.PHONY: help
help: ## Show this help
> @echo "k8s-local — Odoo 19 + Postgres 16/pgvector on a laptop cluster"
> @echo ""
> @echo "  make k8s-up        cluster + image + base manifests  (CLUSTER=$(CLUSTER))"
> @echo "  make k8s-deploy    apply, wait for DB, init schema, wait for Odoo"
> @echo "  make k8s-down      stop workloads, KEEP the data volumes"
> @echo "  make k8s-destroy   delete namespace + volumes (DESTRUCTIVE, asks nothing)"
> @echo "  make k8s-status    pods, services, PVCs and the init job"
> @echo "  make db-shell      psql inside the Postgres pod"
> @echo "  make db-backup     pg_dump -> $(BACKUP_DIR)/<timestamp>.dump"
> @echo "  make logs          follow Odoo logs"
> @echo "  make image         build $(BASE_IMAGE) then $(IMAGE)"
> @echo ""
> @echo "  Variables: CLUSTER=$(CLUSTER) NAMESPACE=$(NAMESPACE) IMAGE=$(IMAGE)"
> @echo "  Without make: bash $(DEPLOY_SCRIPT) <command>   (same commands)"

# -----------------------------------------------------------------------------
# Image
# -----------------------------------------------------------------------------
.PHONY: image
image: ## Build the app image (repo Dockerfile, then the addons layer)
> @echo ">> building $(BASE_IMAGE) from ./Dockerfile (this is the slow one: apt + pip)"
> $(DOCKER) build -t $(BASE_IMAGE) ..
> @echo ">> building $(IMAGE) from Dockerfile.app (adds custom_addons)"
> $(DOCKER) build -f Dockerfile.app -t $(IMAGE) ..
> @echo ">> done: $(IMAGE)"

# -----------------------------------------------------------------------------
# Cluster + deploy
# -----------------------------------------------------------------------------
.PHONY: k8s-up
k8s-up: ## Create/verify the cluster, build+load the image, apply base manifests
> CLUSTER=$(CLUSTER) CLUSTER_NAME=$(CLUSTER_NAME) NAMESPACE=$(NAMESPACE) \
>   IMAGE=$(IMAGE) BASE_IMAGE=$(BASE_IMAGE) KUBECTL=$(KUBECTL) DOCKER=$(DOCKER) \
>   KIND=$(KIND) bash $(DEPLOY_SCRIPT) up

.PHONY: k8s-deploy
k8s-deploy: ## Apply manifests, wait for Postgres, init the schema, wait for Odoo
> NAMESPACE=$(NAMESPACE) IMAGE=$(IMAGE) KUBECTL=$(KUBECTL) \
>   bash $(DEPLOY_SCRIPT) deploy

.PHONY: k8s-status
k8s-status: ## Show pods, services, PVCs and the init job
> $(KUBECTL) get pods,svc,pvc,job -n $(NAMESPACE) -o wide

# -----------------------------------------------------------------------------
# Teardown
# -----------------------------------------------------------------------------
.PHONY: k8s-down
k8s-down: ## Stop the workloads, KEEPING the database + filestore volumes
> $(KUBECTL) scale deployment/odoo -n $(NAMESPACE) --replicas=0
> $(KUBECTL) scale statefulset/postgres -n $(NAMESPACE) --replicas=0
> @echo ""
> @echo "Workloads stopped. The volumes were NOT touched:"
> $(KUBECTL) get pvc -n $(NAMESPACE)
> @echo ""
> @echo "Bring it back with: make k8s-deploy   (start from zero: make k8s-up)"
> @echo "Delete the data with: make k8s-destroy   (DESTRUCTIVE)"

.PHONY: k8s-destroy
k8s-destroy: ## DESTRUCTIVE: delete the namespace, including the data volumes
> @echo "This deletes namespace $(NAMESPACE): the Odoo database AND the filestore."
> @echo "There is no undo. Use 'make db-backup' first if you want the data."
> $(KUBECTL) delete namespace $(NAMESPACE) --ignore-not-found
> @echo "Deleted. Any PersistentVolume left behind (Retain policy) must be"
> @echo "removed by hand:  $(KUBECTL) get pv"

# -----------------------------------------------------------------------------
# Database — the two targets that make the local cluster usable day to day
# -----------------------------------------------------------------------------
.PHONY: db-shell
db-shell: ## Open psql inside the Postgres pod
> @# The password comes from the Secret, not from a flag on the command line, so
> @# it does not end up in the shell history or in `kubectl describe`.
> $(KUBECTL) exec -it statefulset/postgres -n $(NAMESPACE) -- \
>   env PGPASSWORD="$$(cat /run/secrets/db/password)" \
>   psql -U odoo -d odoo

.PHONY: db-backup
db-backup: ## pg_dump the odoo database into ./backups (custom format, verified)
> @mkdir -p $(BACKUP_DIR)
> @# -Fc: custom format, the same format scripts/db-migrate.sh and
> @# docker/initdb tooling already assume (pg_restore -Fc, not plain SQL).
> @# Written inside the pod (the volume is the only place with room), then
> @# copied out and size-checked here.
> $(KUBECTL) exec -n $(NAMESPACE) statefulset/postgres -- \
>   sh -c 'pg_dump -U odoo -Fc --no-owner -d odoo -f /tmp/odoo.dump'
> $(KUBECTL) cp $(NAMESPACE)/postgres-0:/tmp/odoo.dump $(BACKUP_DIR)/odoo-$(shell date +%Y%m%d-%H%M%S).dump
> $(KUBECTL) exec -n $(NAMESPACE) statefulset/postgres -- rm -f /tmp/odoo.dump
> @ls -lh $(BACKUP_DIR)/ | tail -3
> @echo "Restore: see k8s-local/README.md (§ Restore a backup)"

# -----------------------------------------------------------------------------
# Logs
# -----------------------------------------------------------------------------
.PHONY: logs
logs: ## Follow the Odoo container logs
> $(KUBECTL) logs -n $(NAMESPACE) deployment/odoo -f --tail=200

.PHONY: logs-db
logs-db: ## Follow the Postgres container logs
> $(KUBECTL) logs -n $(NAMESPACE) statefulset/postgres -f --tail=200

.PHONY: logs-init
logs-init: ## Show the schema-init Job logs (first boot debugging)
> $(KUBECTL) logs -n $(NAMESPACE) job/odoo-init --tail=200
