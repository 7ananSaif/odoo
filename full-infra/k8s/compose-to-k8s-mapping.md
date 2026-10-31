# Docker Compose → Kubernetes Object Map

Every service in [`docker-compose.yml`](../../docker-compose.yml) and its future
Kubernetes counterpart. This answers the question the exercise asks: *given the
Compose stack that runs today, what object does each piece become once it lives
in the cluster?*

Two columns of truth, because they genuinely differ:

- **Local (kind)** — what we can actually stand up on a laptop with no cloud.
- **Prod (EKS)** — what `full-infra/eks/` + `full-infra/helm/odoo-stack` target, where
  stateful infrastructure is offloaded to managed AWS services.

The rule of thumb behind every row:

| Compose concept | Kubernetes object | Why |
|---|---|---|
| A service that serves traffic | **Deployment + Service** | Pods are disposable; the Service is the stable address. |
| A service with persistent state | **StatefulSet + headless Service** (+ PVC) | Stable identity + its own storage per replica. |
| A service with no inbound port (a consumer) | **Deployment, no Service** | It dials out; nothing dials in. |
| A one-of-a-kind scheduler loop | **Deployment with `replicas: 1`** | Must never run twice. |
| A reverse proxy / TLS terminator | **Ingress + Ingress controller + cert-manager** | Routing and certs are cluster-level concerns. |
| A named volume | **PersistentVolumeClaim** (or managed AWS storage) | Data outlives the container. |
| `env_file` / `environment:` | **ConfigMap + Secret** | See [`config-secret-plan.md`](config-secret-plan.md). |
| `depends_on: service_healthy` | **initContainers + readinessProbes** | No ordering primitive; wait, then retry. |
| `healthcheck:` | **readinessProbe / livenessProbe** | Same idea, first-class in the API. |
| `restart: unless-stopped` | **`restartPolicy: Always`** (Deployment default) | Free once a controller owns the Pod. |
| `profiles: [x]` | **Namespace / Helm value gate** | Opt-in groups of objects. |
| `deploy.resources.limits` | **`resources.requests` / `resources.limits`** | Already the same shape. |
| `logging: json-file` options | **kubelet log rotation / log shipper** | Rotation is a node concern, not a pod one. |

---

## Summary table

| # | Compose service | Image / build | Local (kind) | Prod (EKS) | Notes |
|---|---|---|---|---|---|
| 1 | `odoo` | build `.` | Deployment + ClusterIP Service (+ PVC) | Deployment + Service (Helm chart) | Public web app; cron split out. |
| 2 | `db` | `pgvector/pgvector:0.8.6-pg16-bookworm` | **StatefulSet** + headless Service + PVC | **Amazon RDS** (managed) | `terraform/rds.tf`. |
| 3 | `redis` | `redis:7-alpine` | **StatefulSet** + headless Service + PVC | **Amazon ElastiCache** | `terraform/elasticache.tf`. |
| 4 | `rabbitmq` | `rabbitmq:3.13-management` | **StatefulSet** + headless Service + PVC | **Amazon MQ** | Broker; stateful. |
| 5 | `invoice-ai` | build `./invoice-ai` | Deployment + ClusterIP Service | Deployment + Service | Stateless HTTP API. |
| 6 | `worker` | build `./invoice-ai` | **Deployment, no Service** | Deployment, no Service | AMQP consumer; scales out. |
| 7 | `saas-manager-web` | build `./saas_manger` | Deployment + ClusterIP Service | Deployment + Service | Docker-socket control → K8s API. |
| 8 | `saas-manager-worker` | build `./saas_manger` | **Deployment, no Service** | Deployment, no Service | Celery worker fleet. |
| 9 | `saas-manager-beat` | build `./saas_manger` | **Deployment, `replicas: 1`** | Deployment, `replicas: 1` | Singleton scheduler. |
| 10 | `odoo-control` | build `.` | Deployment + ClusterIP Service | Deployment + Service | Internal `list_db=True`; no host port. |
| 11 | `odoo-master` | build `.` | Deployment, normally `replicas: 0` | Same | Owner-only, on demand. |
| 12 | `nginx` | `nginx:alpine` | Deployment + Service (port-forward / NodePort) | **Ingress** + ALB | Reverse proxy + TLS. |
| 13 | `certbot` | `certbot/certbot:latest` | **cert-manager** `Certificate` | **cert-manager** / ACM | Not a workload you babysit. |
---

## Per-service detail

### 1. `odoo` — the public web app → **Deployment + Service**

Today: `build: .`, binds `127.0.0.1:8069` and `8072` (longpolling/websocket),
mounts `./custom_addons` (addons), `odoo-web-data` (filestore), and
`./docker/odoo.conf`, and runs `odoo --addons-path=... --no-database-list
--dev=reload`.

Kubernetes:

- **Deployment** with `replicas: N` (`N` = how many workers you want). Odoo's
  web tier is stateless *except* for the filestore and the sessions — see below.
- **Service** (ClusterIP) `odoo`, port `8069`, plus a second port `8072` for
  the websocket/longpolling endpoint.
- The `--dev=reload` flag is a laptop-only affordance and is dropped.
- `docker/odoo.conf` → a **ConfigMap** mounted at `/etc/odoo/odoo.conf`.
- `./custom_addons` → **baked into the image** (best) or an `emptyDir`/PVC
  populated by an initContainer. A host bind-mount has no meaning on a cluster
  node.
- Resource limits map 1:1 to `resources.requests`/`limits` (`2G` → `2Gi`).

The two things that must be solved before replicas > 1 compile:

1. **Filestore** — `odoo-web-data` becomes a **PVC**. A `ReadWriteOnce` PVC
   locks the Deployment to one Pod (and one node). To run several replicas you
   need either a `ReadWriteMany` volume (EFS on AWS) or the `s3_storage` addon
   pointing at the S3 bucket the runbook already syncs to.
2. **Cron** — the compose service runs the scheduler in-process. In Kubernetes
   that becomes a **separate Deployment with `replicas: 1`** (or the same image
   with cron enabled and web disabled), so the web replicas never double-run
   scheduled jobs. This mirrors what the compose file already does by hand for
   `odoo-control` and `odoo-master` (`--max-cron-threads=0`).

### 2. `db` — Postgres 16 + pgvector → **StatefulSet** (local) / **RDS** (prod)

Today: a pinned `pgvector/pgvector` image, a named volume `odoo-db-data`, a
startup `command` that sets `shared_preload_libraries`, an initdb mount
(`./docker/initdb`) that runs `CREATE EXTENSION vector` on a fresh volume, and a
`pg_isready` healthcheck.

Kubernetes, **local**:

- **StatefulSet** `db`, one replica, `volumeClaimTemplates` giving it a PVC.
  StatefulSet (not Deployment) because the Pod needs a *stable* name
  (`db-0`) and its own storage that survives rescheduling.
- **Headless Service** `db` (`clusterIP: None`) so clients resolve `db-0.db`.
  Everything else in the stack keeps connecting to the name `db`, so the
  compose env (`HOST=db`) needs no change.
- The initdb files → a **ConfigMap** mounted at
  `/docker-entrypoint-initdb.d` (or run the same `CREATE EXTENSION` from an
  initContainer / Job).
- `POSTGRES_PASSWORD` → **Secret**.

Kubernetes, **prod**: none of the above. `terraform/rds.tf` already provisions a
managed RDS instance; the cluster just points `ODOO_DB_HOST` at its endpoint and
the StatefulSet is not deployed at all (`postgres.enabled: false` in the Helm
values). Managed backups, failover and patching come for free.

> pgvector caveat: if you keep using the pgvector column in prod, RDS must be a
> Postgres engine version/extension that ships `vector`, or the extension is
> installed via RDS's supported-extension mechanism. This is a real constraint,
> not a detail — the vector column silently fails without it.

### 3. `redis` — cache + session store → **StatefulSet** / **ElastiCache**

Today: `redis:7-alpine`, `--appendonly yes`, named volume `redis-data`, a
`redis-cli ping` healthcheck, loopback port 6379.

- **Local**: **StatefulSet** (1 replica, PVC) + headless Service `redis`. The
  Redis *broker/cache* role is small and rarely the point of contention, but it
  is stateful, so it is not a Deployment.
- **Prod**: **Amazon ElastiCache** (`terraform/elasticache.tf`). The app's
  `REDIS_URL` is repointed at the cluster endpoint and no Redis Pod exists.

### 4. `rabbitmq` — the broker → **StatefulSet** / **Amazon MQ**

Today: `rabbitmq:3.13-management`, named volume `rabbitmq-data`,
`rabbitmq-diagnostics ping` healthcheck, management UI on loopback 15672.

- **Local**: **StatefulSet** + headless Service `rabbitmq`. RabbitMQ has real
  cluster-formation semantics (Erlang cookies, queue mirroring) which the
  RabbitMQ Cluster Operator encodes; for a single-node local broker the
  StatefulSet is enough.
- **Prod**: **Amazon MQ** for a managed broker, *or* the **RabbitMQ Cluster
  Operator** if you want a high-availability broker inside the cluster. Either
  way the connect string is `amqp://<user>:<pass>@<host>:5672` and the
  credentials move to a Secret.
- The management UI is not exposed; you reach it with
  `kubectl port-forward pod/rabbitmq-0 15672:15672` when you need it.

### 5. `invoice-ai` — FastAPI extraction API → **Deployment + Service**

Today: `build: ./invoice-ai`, loopback `127.0.0.1:8100`, a
`/healthz` healthcheck, `REDIS_URL`, `INVOICE_AI_*` config, a memory limit.

- **Deployment** `invoice-ai` + **ClusterIP Service** `invoice-ai:8100`. The
  compose file already addresses it as `invoice-ai:8100` on the private network,
  and a ClusterIP Service *is* exactly that private network in Kubernetes — the
  DNS name is even the same. Nothing else changes.
- The `/healthz` healthcheck → `readinessProbe` + `livenessProbe` with an
  `httpGet` on `/healthz`.
- `ANTHROPIC_API_KEY`, `INVOICE_AI_JWT_SECRET` → **Secret**; the rest of
  `INVOICE_AI_*` → **ConfigMap** (already classified in
  [`config-secret-plan.md`](config-secret-plan.md)).
- The `127.0.0.1:8100` host mapping **goes away**. In compose it exists only so
  a host-side deploy pipeline can health-check it; in Kubernetes the readiness
  probe is *in-cluster* and needs no host port.

### 6. `worker` — AMQP consumer → **Deployment, no Service**

Today: same `./invoice-ai` image, `command: python -m app.consumer`,
`depends_on: rabbitmq (healthy)`, no ports.

- **Deployment** with no Service and no ports. It is a queue consumer: it dials
  RabbitMQ and Redis outbound and nothing dials in, so a Service would be a
  meaningless object.
- `depends_on: rabbitmq: service_healthy` has **no direct equivalent**. The
  idiomatic replacement is an **initContainer** that blocks until the broker
  answers, plus the consumer's own reconnect/retry loop. Kubernetes will happily
  start the Pod before RabbitMQ is ready; the code must tolerate that.
- This is the poster child for horizontal scaling: `kubectl scale deployment
  worker --replicas=5` adds consumers, and the broker load-balances deliveries
  across them without any code change. Compose cannot do this at all.
### 7. `saas-manager-web` — control panel web (FastAPI) → **Deployment + Service**

Today: `build: ./saas_manger`, uvicorn on `:8080`, loopback-only, a `/health`
healthcheck, and — the interesting part — it bind-mounts
`/var/run/docker.sock` so the "Apps" page can start/stop/restart sibling compose
services.

- **Deployment** `saas-manager-web` + **ClusterIP Service** on `8080`. Still
  owner-only: instead of a host loopback port, reach it with
  `kubectl port-forward svc/saas-manager-web 8080:8080` (the SSH-tunnel habit
  becomes a port-forward).
- The `/health` healthcheck → readiness/liveness probes.
- `MANAGER_DB_URL` → **Secret** (it embeds credentials); the rest of the
  `SAAS_*`/`ODOO_*` settings → **ConfigMap**.
- **The Docker socket is the one thing that does not translate.** Mounting
  `docker.sock` into a Pod means that Pod can control the *host's* Docker daemon
  — on a cluster it either does not exist or is a serious privilege escalation.
  The Kubernetes-native replacement is to give the Pod a **ServiceAccount with
  RBAC** that lets it patch Deployments/scale workloads, and have
  `app/services/docker_control.py` call the **Kubernetes API** instead of the
  Docker API. Same feature ("restart a tenant's app"), correct mechanism.
  Until that refactor lands, drop the socket mount and the Apps page degrades to
  the "explanation instead of controls" behaviour the compose file already
  supports.

### 8. `saas-manager-worker` — Celery worker → **Deployment, no Service**

Today: `python -m celery ... worker -Q default,updates,backups`, no ports.

- **Deployment**, no Service. Scales out with `kubectl scale` exactly like the
  `worker` service above; queue names are config, not objects.
- Celery needs the broker (`CELERY_BROKER_URL`, Redis DB 2) and result backend
  (DB 3) → **ConfigMap**/Secret, already covered.

### 9. `saas-manager-beat` — Celery beat scheduler → **Deployment, `replicas: 1`**

Today: `python -m celery ... beat`, one instance by construction.

- **Deployment with `replicas: 1`, and it must stay 1.** Two beat schedulers
  double-fire every periodic task. Kubernetes will not stop you from scaling it
  to 2, so the safety is a convention: keep the replica count at 1, or move the
  schedule to a **CronJob** (one Job per tick) if tasks are independent.
- This is the same "singleton scheduler" shape as Odoo's cron and is the reason
  the compose file pins `--max-cron-threads=0` on the non-primary Odoo
  instances.

### 10. `odoo-control` — internal control instance → **Deployment + Service**

Today: the same image, `list_db = True` (`docker/odoo-control.conf`), no host
port, reachable only as `odoo-control:8069` on the private network, cron off.

- **Deployment** + **ClusterIP Service** `odoo-control:8069`. The compose file
  already describes exactly a ClusterIP Service — an internal DNS name that no
  host port exposes. Nothing about the contract changes; the Service DNS name is
  even identical.
- Its config file → **ConfigMap**; it shares the filestore PVC with `odoo`.

### 11. `odoo-master` — owner-only break-glass instance → **Deployment, `replicas: 0`**

Today: behind the `saas-master` profile, started by hand, `list_db = True`, cron
off, loopback port 8070, reached through an SSH tunnel.

- **Deployment** that normally sits at `replicas: 0`; bring it up with
  `kubectl scale deployment odoo-master --replicas=1`, reach it with a
  port-forward, then scale back to 0. The compose profile maps cleanly onto a
  scaled-to-zero Deployment: "defined, but not running".
- It must **not** get an Ingress and must **not** share the public Service —
  same reasoning as the compose comment ("never exposed publicly").

### 12. `nginx` — reverse proxy + TLS → **Ingress (+ controller)**

Today: `nginx:alpine`, `./nginx/conf.d` mounted as templates, ports 80/443,
proxying to `odoo` and `invoice-ai`, terminating Let's Encrypt TLS.

- In Kubernetes the "nginx that fronts everything" is an **Ingress controller**
  (commonly `ingress-nginx`) plus **Ingress** resources; TLS is issued and
  rotated by **cert-manager**, not by a proxy sidecar.
- **Local (kind)**: install the `ingress-nginx` kind variant, apply an Ingress
  with `host: localhost`, and the `extraPortMappings` in `kind-cluster.yaml`
  (host 80/443 → node 80/443) make it reachable at `http://localhost`. For this
  exercise we skip that and use `port-forward` — but this is the real mapping.
- **Prod (EKS)**: the **AWS Load Balancer Controller** turns an Ingress into an
  ALB and ACM (or cert-manager) provides the certificate — see
  `full-infra/eks/aws-load-balancer-controller.md`. The hand-rolled `nginx` container
  disappears entirely.
- If you would rather keep an Nginx you control, it becomes a **Deployment +
  Service of type LoadBalancer** with `nginx/conf.d` as a **ConfigMap**. That is
  a valid but heavier choice; Ingress is the idiomatic one.

### 13. `certbot` — certificate renewal → **cert-manager**

Today: `certbot/certbot`, a `sleep 12h` renew loop, sharing `certbot-www` and
`certbot-conf` volumes with nginx.

- Not a workload you run by hand. It becomes **cert-manager**: a
  `ClusterIssuer` (ACME/Let's Encrypt) plus a `Certificate` object, and
  cert-manager writes the resulting `tls` Secret that the Ingress references.
  Renewal is automatic and needs no sleep loop.
- The `certbot-www` webroot volume exists only for the HTTP-01 challenge that
  cert-manager solves itself; both volumes are retired.

---

## Named volumes → storage

| Compose volume | Contents | Kubernetes |
|---|---|---|
| `odoo-db-data` | Postgres data dir | **PVC** via the `db` StatefulSet — **RDS** in prod. |
| `odoo-web-data` | Odoo filestore (`/var/lib/odoo`) | **PVC**. Needs `ReadWriteMany` (EFS) or the `s3_storage` addon for >1 replica. |
| `rabbitmq-data` | Broker state | **PVC** via the `rabbitmq` StatefulSet — **Amazon MQ** in prod. |
| `redis-data` | AOF append-only file | **PVC** via the `redis` StatefulSet — **ElastiCache** in prod. |
| `certbot-www` | ACME HTTP-01 webroot | retired (**cert-manager** solves the challenge). |
| `certbot-conf` | `/etc/letsencrypt` | retired (**cert-manager** stores certs as a Secret). |
| `saas-manager-backups` | tenant `pg_dump` zips | **PVC** — or an **S3** bucket, which is where backups belong. |

A **PV** is the actual disk; a **PVC** is the request for one. kind binds PVCs to
a default `local-path` provisioner. On EKS the storage class is the **EBS CSI**
driver (per-node `ReadWriteOnce`) — which is exactly why a shared filestore
needs **EFS** instead.

---

## Compose-only concepts and their replacements

| Compose feature used in this stack | Kubernetes replacement |
|---|---|
| `depends_on: {x: {condition: service_healthy}}` | Nothing built-in. Use an **initContainer** that polls the dependency, plus retry/backoff in the app. The Pod may start first; it must cope. |
| `profiles: [saas-manager]` / `[saas-master]` | **Namespaces**, or a Helm value that gates whether the objects are rendered. `odoo-master` in particular = a Deployment at `replicas: 0`. |
| `restart: unless-stopped` / `restart: "no"` | `restartPolicy: Always` (Deployment/StatefulSet default) or `Never`/`OnFailure` for a bare Pod/Job. |
| `ports: "127.0.0.1:8080:8080"` | A ClusterIP Service plus `kubectl port-forward`, or an Ingress. Host loopback binding is not a cluster concept. |
| `build: ./x` | Build the image in CI, push to a registry (ECR), and reference the image by tag/digest. Kubernetes never builds. |
| `bind: ./custom_addons` | Bake into the image, or an EFS/NFS PVC, or an initContainer that clones/copies the addons. |
| `env_file: .env` | **ConfigMap** (non-secret) + **Secret** (secret), or **ExternalSecret** from AWS Secrets Manager. See `config-secret-plan.md`. |
| `logging: {driver: json-file, options: {max-size}}` | The kubelet rotates container logs at the node level; ship them with **Fluent Bit**/Loki for aggregation. There is no per-pod log driver. |
| `deploy.resources.limits` | `resources.requests`/`limits` — the same fields, already familiar. |
| `healthcheck: test: [CMD-SHELL, ...]` | `readinessProbe` (traffic gating) and `livenessProbe` (restart on wedged) — separate concerns Compose merges into one. |
| `/var/run/docker.sock` mount (saas-manager-web) | A **ServiceAccount + RBAC** and calls to the Kubernetes API. Never mount the host daemon socket into a Pod. |

---

## What stays managed AWS (never runs as a Pod)

| Compose service | AWS replacement | Terraform |
|---|---|---|
| `db` | **Amazon RDS** (Postgres) | `full-infra/terraform/rds.tf` |
| `redis` | **Amazon ElastiCache** | `full-infra/terraform/elasticache.tf` |
| `rabbitmq` | **Amazon MQ** (or the RabbitMQ Cluster Operator) | — |
| Odoo filestore | **S3** (`s3_storage` addon) or **EFS** | `full-infra/terraform/s3.tf` |
| `.env` secrets | **AWS Secrets Manager / SSM**, injected via External Secrets | `full-infra/terraform/ssm.tf`, `iam.tf` |
| certificates | **ACM** (via the ALB) or **cert-manager** | `full-infra/terraform/routes.tf` |

The point of the exercise's local cluster is to get the *object model* right —
which things are Deployments, which are StatefulSets, which need a Service and
which do not — before any of it is wired to managed infrastructure.

---

## The one-line summary

Services that answer HTTP → **Deployment + Service**. Services that hold bytes
on disk → **StatefulSet + headless Service + PVC**. Services that only consume a
queue → **Deployment, no Service**. One-off schedulers → **`replicas: 1`**. The
proxy and its certificates → **Ingress + cert-manager**. Everything with a
managed AWS equivalent (Postgres, Redis, RabbitMQ, filestore, secrets) → **the
managed service, referenced by config**, not a Pod.
