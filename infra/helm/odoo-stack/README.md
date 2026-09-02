# odoo-stack Helm Chart

Helm chart for the Odoo ERP stack (Postgres + Odoo web), templated from `values.yaml` rather than hardcoded. Includes:
- **Postgres** as a `StatefulSet` with a `volumeClaimTemplate` (stable identity + durable storage).
- **ConfigMap** for non-sensitive config.
- **Secret** for sensitive values (local placeholders only; prod references an existing Secret).
- **PVCs** (Postgres `pgdata`, Odoo `filestore`).
- **Resource requests/limits** and **readiness/liveness probes** on every container.

## Layout

```
odoo-stack/
  Chart.yaml
  values.yaml            # local defaults
  values.staging.yaml    # staging overlay
  values.production.yaml # production overlay
  templates/
    _helpers.tpl
    configmap.yaml
    secret.yaml
    postgres-statefulset.yaml
    postgres-service.yaml   # headless + ClusterIP
    odoo-deployment.yaml
    odoo-service.yaml
    odoo-pvc.yaml           # filestore
    NOTES.txt
  README.md
```

## Values split by environment

| File | Purpose |
|------|---------|
| `values.yaml` | local defaults (small sizes, `secret.existingSecret: false`, placeholder passwords) |
| `values.staging.yaml` | staging overrides (bigger resources, 2 Odoo replicas, `secret.existingSecret: true`) |
| `values.production.yaml` | production overrides (biggest resources, 3 Odoo replicas, `secret.existingSecret: true`) |

Secrets are never committed: in staging/prod `secret.existingSecret: true` tells the chart to reference an out-of-band Secret (created via AWS Secrets Manager / External Secrets Operator) instead of rendering one.

## Install / upgrade (on kind)

```
# start the cluster
kind create cluster --name odoo-kind

# local (defaults)
helm install odoo infra/helm/odoo-stack

# verify
kubectl get all -l app.kubernetes.io/instance=odoo
kubectl rollout status statefulset/odoo-odoo-stack-postgres

# change a value and upgrade in place
helm upgrade odoo infra/helm/odoo-stack --set odoo.replicaCount=2
```

With environment overlays:

```
helm install odoo infra/helm/odoo-stack -f infra/helm/odoo-stack/values.production.yaml
```

---

## Resource sizing (documented + justified)

Baseline comes from observed usage on the current EC2 deployment. Requests are set to the **sustained working set**; limits provide headroom for bursts and a hard ceiling to protect node neighbors.

### Postgres

| Env | Requests | Limits |
|-----|----------|--------|
| local | cpu `250m`, mem `512Mi` | cpu `1`, mem `1Gi` |
| staging | cpu `500m`, mem `1Gi` | cpu `2`, mem `2Gi` |
| production | cpu `1`, mem `2Gi` | cpu `4`, mem `8Gi` |

- Low initial requests keep Postgres schedulable on a small kind node while still leaving headroom.
- Memory limit at 2x request is a safe guard: Postgres uses memory for `shared_buffers` and work_mem; if it approaches the limit the OOM killer reclaims it rather than starving the node.
- Production doubles again to absorb higher connection counts + larger `work_mem`.

### Odoo web

| Env | Requests | Limits |
|-----|----------|--------|
| local | cpu `500m`, mem `1Gi` | cpu `2`, mem `2Gi` |
| staging | cpu `1`, mem `2Gi` | cpu `3`, mem `4Gi` |
| production | cpu `2`, mem `4Gi` | cpu `6`, mem `8Gi` |

- Odoo workers are memory-heavy (per-worker `--max-cron-threads`, report jobs, attachments). The request is the steady per-pod working set; the limit is 2x to allow a spike (e.g. a large PDF render) without killing the node.
- Production raises both to support 3 replicas under real concurrency.

### Storage

| Component | local | staging | production |
|-----------|-------|---------|------------|
| Postgres `pgdata` | `8Gi` | `20Gi` | `100Gi` |
| Odoo `filestore` | `10Gi` | `20Gi` | `100Gi` |

- Sized from current on-disk growth; the filestore is the Odoo attachments directory and is the slowest-growing but most important to keep.

---

## Probe choices (documented + justified)

### Postgres

- **readiness**: `pg_isready -U <user> -d <db>`
  - Why: `pg_isready` returns success only once the server accepts connections. Kubernetes removes the pod from Service endpoints until the database is genuinely ready to serve — no traffic is routed to a half-initialized DB.
  - `initialDelaySeconds: 15` (lets the first-time initdb + startup complete), `periodSeconds: 10`, `timeoutSeconds: 5`, `failureThreshold: 3`.
- **liveness**: `pg_isready -U <user> -d <db>`
  - Why: if Postgres becomes wedged (e.g. mid-failover, or stuck on a lock), the check fails and the container is restarted rather than serving stale data forever.
  - `initialDelaySeconds: 30` (longer than readiness — don't kill a slow first boot), `periodSeconds: 15`, `timeoutSeconds: 5`, `failureThreshold: 3`.
- A single `exec` probe is used rather than an HTTP one because Postgres has no HTTP health endpoint; `pg_isready` is the Postgres-native check.

### Odoo

- **readiness**: HTTP GET `/web/health` (port 8069)
  - Why: Odoo's `/web/health` returns 200 only when the server is up and initialized. This distinguishes "container running but not yet ready to serve" from "ready". Until readiness passes, no Service endpoints route to the pod.
  - `initialDelaySeconds: 30` (Odoo takes a while to initialize workers), `periodSeconds: 10`, `timeoutSeconds: 5`, `failureThreshold: 3`.
- **liveness**: HTTP GET `/web/health` (port 8069)
  - Why: if Odoo's HTTP layer hangs (workers deadlocked, DB connection stuck), the liveness check fails and the pod is restarted — recovering a genuinely stuck process instead of leaving it taking traffic and answering timeouts.
  - `initialDelaySeconds: 60` (a slow first start must not be misread as dead), `periodSeconds: 15`, `timeoutSeconds: 5`, `failureThreshold: 3`.

> The readiness probe uses a **longer success-window** (initialDelay 30 vs liveness 60) so a pod that is *alive but still booting* is correctly held out of rotation, while a pod that is truly stuck is restarted.

---

## Secrets

- Local (`values.yaml`): `secret.existingSecret: false` renders a `Secret` from `secret.postgresPassword` / `secret.odooDbPassword`. These are explicitly **placeholders** (`change-me`) — never commit real values.
- Staging/Production: `secret.existingSecret: true` references `secret.name`. Provision that Secret out-of-band (AWS Secrets Manager + External Secrets Operator) so secrets never live in git or the release manifest.

## Configuration

- `config.odooDbHost` / `config.odooDbPort` / `config.odooDbUser` feed the Odoo entrypoint env (`HOST`, `PORT`, `USER`).
- `config.extra` adds extra non-sensitive key/values to the ConfigMap.
- `odoo.extraEnv`, `odoo.extraVolumes`, `odoo.extraVolumeMounts` let you add app-specific env/volumes (e.g. custom addons directory).
