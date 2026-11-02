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

## 0. What runs

**The whole application, including the AI pipeline.** Every service in
`docker-compose.yml` that the extraction path needs has an equivalent here:

| Component | Kind | Why |
|---|---|---|
| `odoo` | Deployment + Service (NodePort 30080) | the app: Odoo 19 + `custom_addons` |
| `postgres` | StatefulSet + PVC (8Gi) + Service | PostgreSQL 16 with pgvector |
| `odoo-init` | Job | one-shot `--init=base`, creates the schema |
| `odoo-filestore` | PVC (10Gi) | `/var/lib/odoo` — attachments |
| `rabbitmq` | StatefulSet + PVC (1Gi) + Service | job queue for `extract.request` |
| `redis` | StatefulSet + PVC (1Gi) + Service | LLM cache (AOF on) |
| `invoice-ai` | Deployment + Service (8100) | FastAPI: OCR → Claude → RAG |
| `invoice-ai-worker` | Deployment | AMQP consumer that calls Claude |

Wiring, all in the ConfigMap/Secrets so it needs no post-deploy clicking:

| Setting | Value | Read by |
|---|---|---|
| `INVOICE_AI_LLM_SERVICE_URL` | `http://invoice-ai:8100` | Odoo (`llm_service.py`) |
| `INVOICE_AI_JWT_SECRET` | `odoo-ai` Secret, same value both sides | Odoo + invoice-ai |
| `INVOICE_AI_JWT_AUDIENCE` | `invoice-ai` | invoice-ai (`/v1/extract` 401s otherwise) |
| `RABBITMQ_HOST` / `_PORT` | `rabbitmq` / `5672` | Odoo outbox + worker |
| `REDIS_URL` | `redis://redis:6379/0` | invoice-ai + worker |

**Not run**: `saas-manager-web / -worker / -beat` and `odoo-master` /
`odoo-control`. Those are multi-tenant control-plane services with their own
compose profiles, not part of running one instance.

**One placeholder you must fill for real extractions:** `ANTHROPIC_API_KEY` in
`base/01-secret.yaml` is empty on purpose. With it empty the stack runs,
`/healthz` answers, the worker consumes, and each extraction returns 503 and is
queued for retry — a visible failure, not a silent one. Set a real key:

```bash
kubectl create secret generic odoo-ai -n odoo-local \
  --from-literal=INVOICE_AI_JWT_SECRET="$(openssl rand -hex 32)" \
  --from-literal=ANTHROPIC_API_KEY="sk-ant-..." \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deployment/odoo deployment/invoice-ai deployment/invoice-ai-worker -n odoo-local
```

(Replacing that Secret rotates the JWT secret too — both sides read it from the
same object, so they can never drift apart.)

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
bash deploy/local-k8s.sh up          # docker-desktop (default)
bash deploy/local-k8s.sh deploy
```

The cluster may also be given as the **second argument**, which is the reliable
way to pick one:

```bash
bash deploy/local-k8s.sh up kind
bash deploy/local-k8s.sh deploy kind
```

(The argument exists because an environment variable set in PowerShell does not
reach a WSL bash process — only names in `WSLENV` are forwarded — so
`$env:CLUSTER="kind"` silently fell back to the default.)

### On kind

```bash
cd k8s-local
make k8s-up CLUSTER=kind
make k8s-deploy CLUSTER=kind      # forward CLUSTER on BOTH commands

# or, without make:
bash deploy/local-k8s.sh up kind
bash deploy/local-k8s.sh deploy kind
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

Login: **admin / admin** — that is the user `--init=base` creates. Change the
password straight away (Preferences → Account Security), because a NodePort on
Docker Desktop is reachable by anything running on your machine.

`--without-demo=all` means there is no sample data: base modules only, and an
empty chart of accounts until you install more apps.

---

## 4. Day-to-day commands

```bash
make k8s-status    # pods, services, PVCs, jobs
make logs          # follow Odoo
make logs-ai       # follow invoice-ai (FastAPI)
make logs-worker   # follow the AMQP extraction worker
make logs-queue    # follow RabbitMQ
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
| `make: missing separator` | a recipe line does not start with the file's recipe prefix, or the file was checked out with CRLF (which turns the prefix `>` into `>\r`) | keep the `>` prefix on every recipe line; `.gitattributes` pins `Makefile` to LF — re-checkout if you see CRLF |
| `bind: address already in use` on 30080 | something else owns the NodePort | change `nodePort` in `08-odoo-service.yaml`, or use port-forward |
| `\r: command not found` in the script | CRLF line endings | `git config core.autocrlf false` and re-checkout, or `dos2unix deploy/local-k8s.sh` |
