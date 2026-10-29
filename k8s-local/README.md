# k8s-local — the stack on Docker Desktop Kubernetes or kind

Odoo 19 + the `invoice_agent` addon, on a laptop cluster, with a **real
persistent volume** for PostgreSQL so your data survives restarts.

No AWS. No EKS. No cost beyond the laptop.

| What | Where |
|---|---|
| Manifests | `k8s-local/base/` (kustomize) |
| Commands | `k8s-local/Makefile` → delegates to `../deploy/local-k8s.sh` |
| Cluster config (kind) | `k8s-local/kind-cluster.yaml` |
| App image | `k8s-local/Dockerfile.app` (thin layer over the repo's `./Dockerfile`) |

---

## 0. What runs, and what deliberately does not

**Runs** — the two things this option promises, and nothing else:

| Component | Kind | Why |
|---|---|---|
| `odoo` | Deployment + Service (NodePort 30080) | the app: Odoo 19 + `custom_addons` |
| `postgres` | StatefulSet + PVC (8Gi) + Service | PostgreSQL 16 with pgvector |
| `odoo-init` | Job | one-shot `--init=base`, creates the schema |
| `odoo-filestore` | PVC (10Gi) | `/var/lib/odoo` — attachments |

**Does not run** — the rest of `docker-compose.yml` (Redis, RabbitMQ, and the
`invoice-ai` / `worker` / `saas-manager` services). Those are separate services
with their own compose definitions, and pulling them in would double the scope
of a "run my app locally" exercise. If you want them here, they map 1:1 onto
`Deployment` + `Service` objects using the same patterns as `07-odoo-deployment.yaml`.

Consequence, stated plainly: **the AI extraction pipeline will not work in this
cluster** — Odoo will run, the UI works, bills can be entered by hand, but the
"upload → extract" path needs `invoice-ai` + RabbitMQ + Redis. The full stack
still runs with `docker compose up -d` at the repo root.

---

## 1. Prerequisites

| Tool | Check | Notes |
|---|---|---|
| Docker Desktop | `docker info` | Engine must be **running**, not just installed |
| kubectl | `kubectl version --client` | any recent version |
| kind (optional) | `kind version` | only if you pick the kind cluster |
| GNU make (optional) | `make --version` | ≥3.82. Without it, use the script directly |
| bash | `bash --version` | Git for Windows ships one |

Pick **one** cluster:

* **Docker Desktop Kubernetes** (default) — Settings → Kubernetes → *Enable
  Kubernetes* → Apply & Restart. Then `kubectl config use-context docker-desktop`.
* **kind** — nothing to enable; `k8s-up` creates the cluster from
  `kind-cluster.yaml`.

---

## 2. Deploy

### With make

```bash
cd k8s-local

make k8s-up        # cluster check + build image + load into kind
make k8s-deploy    # apply, wait for Postgres, init schema, wait for Odoo
```

`make k8s-up` takes **5–15 minutes the first time**: it builds the repo's own
`./Dockerfile`, which runs `apt-get` (tesseract, ghostscript, poppler) and
`pip install` (anthropic, boto3, pika, …). Subsequent runs reuse the layer.

### Without make (this machine has no `make`)

Same operations, same script the Makefile calls:

```bash
bash deploy/local-k8s.sh up
bash deploy/local-k8s.sh deploy
```

### On kind

```bash
cd k8s-local
make k8s-up CLUSTER=kind
make k8s-deploy
```

`k8s-up` creates the cluster if it does not exist and runs
`kind load docker-image` — a kind node has its own containerd and cannot see
images built on the host. Docker Desktop shares its image store, so nothing is
loaded there.

---

## 3. Open it

| Cluster | URL |
|---|---|
| Docker Desktop | <http://localhost:30080> |
| kind | <http://localhost:8081> |
| either, no NodePort | `kubectl port-forward -n odoo-local svc/odoo 8069:8069` → <http://localhost:8069> |

Login: the database was initialised with `--without-demo=all`, so no demo data
exists — set an admin password on first visit with:

```bash
kubectl exec -n odoo-local deployment/odoo -- \
  odoo shell -d odoo --no-http < /dev/null
```

…or simply use Odoo's *Set a password* flow on the login page if the admin user
already exists (it does; base init creates `admin` with an unusable password
plus the `admin_passwd` gate). The shortest reliable path on a fresh local DB:

```bash
kubectl exec -it -n odoo-local deployment/odoo -- odoo shell -d odoo
# then, at the >>> prompt:
#   env['res.users'].browse(2).password = 'admin'
```

---

## 4. Day-to-day commands

```bash
make k8s-status    # pods, services, PVCs, jobs
make logs          # follow Odoo
make logs-db       # follow Postgres
make logs-init     # the schema-init Job (first-boot debugging)
make db-shell      # psql inside the Postgres pod
make db-backup     # pg_dump -Fc -> ./backups/odoo-<timestamp>.dump
make k8s-down      # stop workloads, KEEP the data
make k8s-destroy   # DESTRUCTIVE: delete namespace + volumes (asks 'yes')
```

`make db-shell` authenticates with the password already in the container's
environment (`PGPASSWORD="$POSTGRES_PASSWORD"`) — no credential is typed on a
command line, so nothing leaks into shell history.

---

## 5. Where the data lives, and what survives what

PostgreSQL data is a `PersistentVolumeClaim` created by the StatefulSet
(`pgdata-postgres-0`); the filestore is the `odoo-filestore` PVC. The cluster's
default StorageClass provisions the `PersistentVolume` on first use — kind
ships `standard` (local-path), Docker Desktop ships `hostpath`. You do **not**
need to create a PV by hand on either. (For a cluster with no provisioner, see
`optional/static-pv.yaml`, which is a template, not something this stack uses.)

| Action | Database + filestore |
|---|---|
| `kubectl delete pod` | **survives** |
| `kubectl rollout restart deployment/odoo` | **survives** |
| `make k8s-deploy` again | **survives** (values, not data) |
| `make k8s-down` | **survives** (scales to 0, never deletes PVCs) |
| Docker Desktop restart | **survives** |
| `make k8s-destroy` | **destroyed** (namespace delete takes the PVCs) |
| `kind delete cluster` | **destroyed** |

Prove it yourself:

```bash
make db-shell
# odoo=# CREATE TABLE keepme(x int); INSERT INTO keepme VALUES (42);
make k8s-down
make k8s-deploy
make db-shell
# odoo=# SELECT * FROM keepme;   -- still 42
```

---

## 6. Restore a backup

```bash
# 1. copy the dump into the pod
kubectl cp backups/odoo-<timestamp>.dump odoo-local/postgres-0:/tmp/restore.dump

# 2. restore over the live database
kubectl exec -n odoo-local statefulset/postgres -- sh -c \
  'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
   --clean --if-exists --no-owner /tmp/restore.dump'

# 3. Odoo must reconnect: the restored schema replaced the live one
kubectl rollout restart deployment/odoo -n odoo-local
```

`--clean --if-exists` drops and recreates the objects in the dump; it is the
same form `docs/runbooks/db-migration.md` uses for the RDS restore.

---

## 7. How this maps onto the other two options

| Concern | k8s-local (here) | lite-infra | full-infra |
|---|---|---|---|
| Orchestrator | laptop Kubernetes | Docker Compose on one Lightsail/EC2 box | EKS |
| Database | Postgres StatefulSet + PVC | Postgres container + volume | RDS |
| Secrets | in-repo placeholder Secret | `.env` on the instance | AWS Secrets Manager + External Secrets |
| Exposure | NodePort / port-forward | instance public IP + nginx | ALB + Route 53 |
| Cost | $0 | ≈$5/month | $$$ |

The probes, worker sizing and `--init=base` gate are the same decisions the Helm
chart in `full-infra/helm/odoo-stack` makes, and the comments cite the same
measurements — the three options should not disagree about how Odoo is run.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Pod `ImagePullBackOff` / `ErrImageNeverPull` | image not in the node | `make k8s-up` again (kind needs `kind load docker-image`) |
| Odoo Running but never Ready | schema not initialised | `make logs-init`; re-run `make k8s-deploy` |
| `odoo-init` fails, `could not connect` | Postgres still starting | it retries 6 times; if it keeps failing, `make logs-db` |
| PVC `Pending` | no default StorageClass | `kubectl get storageclass`; see `optional/static-pv.yaml` |
| `exec format error` on ARM (Apple silicon) | the digest in the StatefulSet is amd64 | drop `@sha256:…` from the image in `04-postgres-statefulset.yaml` |
| `make: missing separator` | tabs were converted to spaces | this Makefile uses `.RECIPEPREFIX = >`; if you edited it, keep the `>` prefix |
| `bind: address already in use` on 30080 | something else owns the NodePort | change `nodePort` in `08-odoo-service.yaml`, or use port-forward |
| `\r: command not found` in the script | CRLF line endings | `git config core.autocrlf false` and re-checkout, or `dos2unix deploy/local-k8s.sh` |
