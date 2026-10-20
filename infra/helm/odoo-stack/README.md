# odoo-stack Helm Chart

Helm chart for the Odoo ERP stack (Postgres + Odoo web), templated from `values.yaml` rather than hardcoded. Includes:

- **Postgres** as a `StatefulSet` with a `volumeClaimTemplate` (stable identity + durable storage).
- **ConfigMap** for non-sensitive config.
- **Secret** for sensitive values (local placeholders only; prod references an existing Secret).
- **PVCs** (Postgres `pgdata`, Odoo `filestore`).
- **Resource requests/limits** on every container.
- **Three probes on every container** — `startupProbe`, `readinessProbe`, `livenessProbe` — each answering a different question (see [Probe choices](#probe-choices-documented--justified)).

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
| `values.production.yaml` | production overrides (biggest resources, 3 Odoo replicas, `secret.existingSecret: true`, `postgres.enabled: false` because RDS is the database) |

Secrets are never committed: in staging/prod `secret.existingSecret: true` tells the chart to reference an out-of-band Secret (created via AWS Secrets Manager / External Secrets Operator) instead of rendering one.

## Two values that decide whether a release ever becomes ready

Both of these were added after a first production install failed with nothing but
`release odoo failed, and has been uninstalled due to atomic being set: context deadline exceeded`.

### 1. `odoo.workers` must be explicit

Left unset, Odoo sizes its worker pool from `multiprocessing.cpu_count()`, which reports the
**node's** core count and ignores `limits.cpu`. On a 16 vCPU EKS node that is `2n+1 = 33` workers
under an 8Gi limit: the cgroup OOM-kills them one after another, the container restarts, and the pod
never reports ready. The chart therefore always passes `--workers` (and `--max-cron-threads`,
`--db_maxconn`, `--proxy-mode`) as explicit `args`.

`maxCronThreads` is per replica. Odoo claims each cron job with a row lock
(`ir.cron._acquire_one_job`), so `1` on three replicas does not run a job three times.

### 2. The filestore must be shared by every replica

`odoo.filestore.accessMode` defaults to `ReadWriteOnce`, which is correct for one replica on a block
volume (kind `local-path`, EBS `gp3`). It is **wrong** for more than one:

- An EBS volume attaches to a single node. A second replica scheduled elsewhere stays in
  `ContainerCreating` with `Multi-Attach error` forever, so the rollout never completes and a
  `--wait`/`--atomic` install expires.
- The staging and production overlays therefore set `accessMode: ReadWriteMany` and
  `storageClassName: efs-sc`. That requires the `aws-efs-csi-driver` addon and an `efs-sc`
  StorageClass built from an EFS filesystem in the node VPC. Without it the PVC stays `Pending` and
  the pods never schedule.

`podSecurityContext.fsGroup: 101` is what makes the mount writable: both EBS and EFS deliver a
`root:root` directory, and the image runs as the unprivileged `odoo` user (uid 100, gid 101).

The filestore PVC carries `helm.sh/resource-policy: keep`, so attachments survive a failed-install
uninstall or an explicit `helm uninstall`.

## What the deploy pipeline guarantees around this chart

`.github/workflows/deploy.yml` no longer uses `helm upgrade --atomic`: atomic uninstall deletes the
pods, events and logs at the exact moment they are the only diagnostic. The equivalent guarantee is
explicit:

1. `helm lint` and `helm template` (output kept as `rendered.yaml`).
2. **Cluster prerequisites** read from that rendered manifest: the referenced Secret exists and has a
   non-empty `ODOO_DB_PASSWORD`, and the filestore StorageClass exists.
3. **Database preflight** (`infra/k8s/odoo-db-preflight-job.yaml`): a one-shot Job using the same
   image, Secret and network path as Odoo, which fails in ~30s if the `odoo` database is missing,
   unreachable, or has no `ir_module_module` table. The chart's readiness probe cannot detect any of
   those: it dials the `postgres` maintenance database, which RDS always ships.
4. `helm upgrade --install --wait --timeout 12m`.
5. On failure: full diagnostics (pods, PVCs, events, `describe`, current and previous container logs)
   uploaded as an artifact, then rollback to the newest **deployed** revision, or uninstall if this
   run created the release.

## Install / upgrade (on kind)

```
# start the cluster
kind create cluster --config infra/k8s/kind-cluster.yaml --image kindest/node:v1.37.0

# local (defaults)
helm install odoo infra/helm/odoo-stack

# verify
kubectl get all -l app.kubernetes.io/instance=odoo
kubectl rollout status statefulset/odoo-odoo-stack-postgres
kubectl rollout status deployment/odoo-odoo-stack-odoo

# change a value and upgrade in place
helm upgrade odoo infra/helm/odoo-stack --set odoo.replicaCount=2
```

With environment overlays:

```
helm install odoo infra/helm/odoo-stack -f infra/helm/odoo-stack/values.production.yaml
```

`config.odooDbHost` is **empty by default**, which means "the Postgres Service this chart renders"
(`<fullname>-postgres`). Set it explicitly only when `postgres.enabled: false`, where there is no
in-cluster Service to fall back to (production points it at the RDS endpoint).

### First boot on an empty database

The container starts with `--database=<odoo.dbName>` because Odoo's `/web/health` answers **500 while
no database is loaded** (the request needs a registry, and an empty server has none). A brand-new
Postgres still has no Odoo schema, so initialize it **once**:

```
kubectl -n <ns> run odoo-init --image=odoo:17.0 --restart=Never \
  --env=HOST=<release>-odoo-stack-postgres --env=PORT=5432 \
  --env=USER=odoo --env=PASSWORD=<the same password> \
  -- odoo -d odoo -i base --stop-after-init --without-demo=all --no-http
kubectl -n <ns> wait --for=condition=Succeeded pod/odoo-init --timeout=300s
kubectl -n <ns> delete pod odoo-init
```

Two details that cost real time if you get them wrong:

- **Pass credentials as `HOST`/`PORT`/`USER`/`PASSWORD` env vars, not as `--db_host` flags.** The
  `odoo` image ships an `/etc/odoo/odoo.conf` whose `db_host` wins over the flag, so a hand-passed
  `--db_host` is silently ignored and Odoo tries to resolve the literal host `db`. The entrypoint
  appends the `--db_*` flags from those env vars last, which does take effect.
- The Deployment does exactly the same, which is why it sets `args:` for `--database` and never
  `command:` — overriding `command` would replace `docker-entrypoint.sh` and lose the DB flags.

In production the database is expected to exist and be initialized already (RDS, carried over by the
runbook), so the manual step above is local-only. That expectation is now *checked* rather than
assumed: the deploy pipeline runs `infra/k8s/odoo-db-preflight-job.yaml` before `helm upgrade`, and
it fails in about 30 seconds — with a message naming the missing table — if the `odoo` database is
absent, unreachable, or has no `ir_module_module`.

---

## Resource sizing (documented + justified)

### Where the baseline comes from

The current production stack runs on a single EC2 host under `docker-compose.yml`. Compose already
declares a reservation and a limit per service, and those two numbers are the only *measured*
statement anyone has made about what this workload needs:

| Compose service | `deploy.resources.reservations.memory` | `deploy.resources.limits.memory` |
|---|---|---|
| `odoo` | 512M | 2G |
| `db` | 256M | 1G |

So the translation rule is deliberately mechanical, and every number below can be traced back to it:

- **compose `reservations.memory` → Kubernetes `requests.memory`** — the floor the workload is
  guaranteed. In Kubernetes this is also what the scheduler reserves on a node and what decides
  which pods are evicted first under node pressure, so it must match the real guarantee, not be
  inflated "for safety".
- **compose `limits.memory` → Kubernetes `limits.memory`** — the hard cgroup ceiling. 1:1, no change.
- **CPU has no compose equivalent** (compose never limited CPU on this host), so CPU is derived from
  the memory ratio and the kind node's capacity: Odoo gets `500m`/`2`, Postgres `250m`/`1`.
- **staging/production scale from the local numbers** by the replica counts and expected concurrency
  of those environments, not from a fresh guess.

### The resulting numbers

**Postgres**

| Env | Requests | Limits |
|-----|----------|--------|
| local | cpu `250m`, mem `256Mi` | cpu `1`, mem `1Gi` |
| staging | cpu `500m`, mem `1Gi` | cpu `2`, mem `2Gi` |
| production | cpu `1`, mem `2Gi` | cpu `4`, mem `8Gi` |

- Local mirrors compose exactly (`256M` reservation → `256Mi`; `1G` limit → `1Gi`), which keeps the
  pod schedulable on a small kind node.
- The memory limit is 2–4× the request (4× local and production, 2× staging on a larger base), and
  that headroom is intentional for a database: Postgres sizes `shared_buffers` and `work_mem` from
  the memory it is allowed to touch, and it will happily use it. The limit is the guard that keeps a
  runaway query from taking the node with it.
- Production doubles again to absorb higher connection counts and larger `work_mem`.

**Odoo web**

| Env | Requests | Limits |
|-----|----------|--------|
| local | cpu `500m`, mem `512Mi` | cpu `2`, mem `2Gi` |
| staging | cpu `1`, mem `2Gi` | cpu `3`, mem `4Gi` |
| production | cpu `2`, mem `4Gi` | cpu `6`, mem `8Gi` |

- Local again mirrors compose (`512M` reservation → `512Mi`; `2G` limit → `2Gi`).
- Odoo workers are memory-heavy (per-worker overhead, report jobs, attachments). The request is the
  steady per-pod working set; the limit is 2–4× that (4× local, 2× staging/production on a larger
  base) so a large PDF render can spike without the pod being killed mid-request.
- Production raises both to support 3 replicas under real concurrency.

> Because request < limit, these pods are **Burstable**, not Guaranteed. That is the correct QoS class
> for an interactive web tier and a database that both need to burst: Guaranteed would require
> request == limit, which would mean never allowing a report render to use spare capacity.

### Storage

| Component | local | staging | production |
|-----------|-------|---------|------------|
| Postgres `pgdata` | `8Gi` | `20Gi` | `100Gi` |
| Odoo `filestore` | `10Gi` | `20Gi` | `100Gi` |

- Sized from current on-disk growth; the filestore is the Odoo attachments directory and is the
  slowest-growing but most important to keep.

---

## Probe choices (documented + justified)

Three probes, three different questions. Conflating them is how a "health check" becomes the cause
of an outage:

| Probe | Question it answers | What a failure causes |
|---|---|---|
| `startupProbe` | Has this process finished booting? | **No restart, no traffic change** — the other two probes are simply held off until it passes or its budget is spent. |
| `readinessProbe` | May the Service send traffic to this pod *right now*? | Pod is removed from the Service's endpoints. **The process is not restarted.** |
| `livenessProbe` | Is this process wedged and in need of a restart? | Container is killed and restarted. |

### Odoo

The three probes intentionally do **not** hit the same URL. Odoo's health route
(`addons/web/controllers/home.py`) behaves like this:

```python
@http.route('/web/health', type='http', auth='none', save_session=False)
def health(self, db_server_status=False):
    health_info = {'status': 'pass'}
    status = 200
    if db_server_status:
        try:
            odoo.sql_db.db_connect('postgres').cursor().close()
            health_info['db_server_status'] = True
        except psycopg2.Error:
            health_info['db_server_status'] = False
            health_info['status'] = 'fail'
            status = 500
    ...
```

- Plain `/web/health` returns **200 as long as the WSGI process replies** — it never touches the
  database.
- `/web/health?db_server_status=true` additionally opens a connection to the `postgres` maintenance
  database and returns **500 when it cannot connect**.

That asymmetry drives the whole design:

| Probe | Kind | Check | Timings | Why |
|---|---|---|---|---|
| startup | httpGet | `/web/health` | period `5`, timeout `3`, failureThreshold `60` | 300 s budget for the first boot (module install/upgrade). Plain route: booting does not need the DB yet, and a failure here should only ever mean "still starting". |
| readiness | **exec** | `python3` → `http://127.0.0.1:8069/web/health?db_server_status=true` | period `10`, timeout `5`, failureThreshold `2` | DB-aware. A pod that cannot reach Postgres cannot serve a login or any ORM request, so it is pulled out of the Service's endpoints and the healthy replicas take the traffic. |
| liveness | httpGet | `/web/health` | period `15`, timeout `5`, failureThreshold `3` | **Deliberately no DB check.** If a brief database outage flipped readiness *and* liveness, every Odoo pod would be restarted at once and a recoverable blip would become a cluster-wide crash loop. Only a hung WSGI process fails this — and only that deserves a restart. |

#### Why readiness is an `exec` probe and not an `httpGet`

An `httpGet` probe **cannot carry a query string**. `path` is put into a
`url.URL{Path: ...}` and Go percent-encodes `?` as `%3F`, so the request line becomes
`GET /web/health%3Fdb_server_status=true`. The kubelet says so itself — its probe description reads:

```
Readiness: http-get http://:http/web/health%3Fdb_server_status=true delay=0s timeout=5s period=10s
```

Werkzeug decodes that back into a literal path segment, which matches no route, so the pod would
either 404 forever (never ready) or — if a server tolerated it — silently answer the plain health
check and never notice the database was gone. Both outcomes defeat the point.

The chart therefore runs the check from inside the container, where the URL is untouched:

```yaml
readinessProbe:
  exec:
    command:
      - python3
      - -c
      - "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8069/web/health?db_server_status=true', timeout=5)"
```

`urllib` raises on the 500 that Odoo returns when it cannot reach Postgres, which exits non-zero and
fails the probe. `python3` is present in the official `odoo` image (it is a Python application), so no
extra binary has to be baked in.

**No `initialDelaySeconds` anywhere.** The previous revision used `initialDelaySeconds: 30/60` as a
substitute for a startup probe, which is a guess: too short and a slow first boot is killed, too long
and every restart waits needlessly. A `startupProbe` with a real budget expresses the same intent
correctly, and Kubernetes holds readiness and liveness off until it succeeds — so the delay is
implicit and exact.

> `/web/health?db_server_status=true` connects to the database named `postgres`. RDS ships that
> maintenance database by default. If a managed Postgres ever does not, set
> `odoo.probes.readiness.path` to plain `/web/health` for that environment and accept that readiness
> then only proves the HTTP layer is up.

### Postgres

Postgres has no HTTP endpoint, so `pg_isready` is the native check: it opens a TCP connection and
asks the server whether it is accepting connections. Exit `0` = accepting, `1` = rejecting
(starting up / shutting down), `2` = no response, `3` = no attempt.

| Probe | Check | Timings | Why |
|---|---|---|---|
| startup | `pg_isready -U odoo -d odoo` | period `5`, timeout `5`, failureThreshold `60` | 300 s budget. A fresh `initdb` is seconds; replaying WAL on a 100 Gi volume after an unclean shutdown is minutes. Without this, that recovery would be misread as a wedged database and the pod would be killed mid-replay — repeatedly. |
| readiness | `pg_isready -U odoo -d odoo` | period `10`, timeout `5`, failureThreshold `3` | Until it passes, the ClusterIP Service has no endpoints for this pod, so Odoo is never routed to a database that is still starting up or shutting down. |
| liveness | `pg_isready -U odoo -d odoo` | period `15`, timeout `5`, failureThreshold `4` | A postmaster that has stopped accepting connections altogether is wedged and only a restart clears it. A slightly higher `failureThreshold` than readiness keeps a brief checkpoint storm from triggering a restart. |

The command lives in the `odoo-stack.postgresProbe` helper in `_helpers.tpl`, so the three probes can
never drift onto different checks. The user/database come from `postgres.user` / `postgres.database`.

### Why `pg_isready` for readiness rather than readiness-by-server-role

This is a single-replica StatefulSet behind a Service, not a Patroni cluster with a primary/standby
split — there is no "wrong node" to route away from, only "not ready yet". `pg_isready` is exactly
the check that answers that question, and it needs no credentials.

---

## Rolling updates and shutdown

- `strategy.rollingUpdate.maxUnavailable: 0`, `maxSurge: 1` — a new Odoo pod must pass readiness
  before an old one is terminated, so a rollout never dips below the desired replica count serving
  traffic. Without `maxUnavailable: 0` the default is 25%, which on `replicas: 1` means a window with
  **no** ready pod.
- `terminationGracePeriodSeconds: 60` on both — in-flight requests (and a report render) get time to
  finish on `SIGTERM` instead of being cut off at the default 30 s; Postgres gets time to flush
  cleanly instead of being `SIGKILL`ed mid-checkpoint.

---

## Secrets

- Local (`values.yaml`): `secret.existingSecret: false` renders a `Secret` from
  `secret.postgresPassword` / `secret.odooDbPassword`. These are explicitly **placeholders**
  (`change-me`) — never commit real values.
- Staging/Production: `secret.existingSecret: true` references `secret.name`. Provision that Secret
  out-of-band (AWS Secrets Manager + External Secrets Operator) so secrets never live in git or the
  release manifest.

## Configuration

- `config.odooDbHost` / `config.odooDbPort` / `config.odooDbUser` feed the Odoo entrypoint env
  (`HOST`, `PORT`, `USER`). An empty `config.odooDbHost` resolves to the chart's own Postgres Service.
- `config.extra` adds extra non-sensitive key/values to the ConfigMap.
- `odoo.extraEnv`, `odoo.extraVolumes`, `odoo.extraVolumeMounts` let you add app-specific env/volumes
  (e.g. a custom addons directory).

---

## Verification (recorded from this environment)

`helm lint` passes for all three value sets, and rendering every environment gives **two containers
with `startupProbe` + `readinessProbe` + `livenessProbe` and a `resources` block each** (one container
in production, where `postgres.enabled: false`).

```
$ helm lint infra/helm/odoo-stack
1 chart(s) linted, 0 chart(s) failed

$ kubectl -n probetest get deploy probetest-odoo-stack-odoo -o json   # parsed highlights
container: odoo
requests: {"cpu":"500m","memory":"512Mi"}
limits:   {"cpu":"2","memory":"2Gi"}
startup:   path=/web/health period=5 fail=60
readiness: exec  python3 .../web/health?db_server_status=true  period=10 fail=2
liveness:  path=/web/health period=15 fail=3
strategy:  maxUnavailable=0 maxSurge=1 grace=60
```

### The probe distinction, proven by removing the database

Both pods reached `1/1`, then the Postgres StatefulSet was scaled to `0` — no restart of Odoo, just
the database gone — and back to `1`:

```
# 1. healthy: both ready, Service has an endpoint
probetest-odoo-stack-odoo-...-dkc8l   1/1   Running   0
probetest-odoo-stack-postgres-0       1/1   Running   0

# 2. postgres scaled to 0 -> readiness fails, liveness does NOT
$ kubectl -n probetest scale statefulset probetest-odoo-stack-postgres --replicas=0
probetest-odoo-stack-odoo-...-dkc8l   0/1   Running   0        <- not ready
$ kubectl -n probetest get endpoints probetest-odoo-stack-odoo
NAME                        ENDPOINTS   AGE
probetest-odoo-stack-odoo               <- empty: out of rotation
restarts: 0                               <- liveness never fired

# 3. postgres scaled back to 1 -> recovered without a restart
probetest-odoo-stack-odoo-...-dkc8l   1/1   Running   0
probetest-odoo-stack-postgres-0       1/1   Running   0
endpoints: 10.244.0.20 ready=True
```

That is the whole point of separating the two probes:

- **`RESTARTS 0`** while the database was gone. The liveness probe is the plain `/web/health`, which
  still answered 200 because the WSGI process was fine — so nothing was killed during an outage that
  a restart could not have fixed.
- **`0/1` and an empty endpoint list** in the same window. The readiness probe is the DB-aware one, so
  the pod stopped receiving traffic the moment it could not reach Postgres, and the Service sent
  requests only to replicas that could actually serve them.
- **No restart to recover.** When Postgres came back, readiness passed again on its own and the
  endpoint was re-added — the pod was never torn down and rebuilt to achieve that.

`postgres-0` reaching `1/1` is likewise its `pg_isready` startup probe succeeding and then the
readiness probe keeping it in the Service: a pod that has *finished starting* and a pod that *may take
clients* are not the same state.
