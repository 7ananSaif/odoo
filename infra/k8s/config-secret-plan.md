# ConfigMap / Secret Migration Plan — Odoo Stack

This plan maps every key in the current `.env` to its future Kubernetes home:
**ConfigMap** (non-sensitive), **Secret** (sensitive), or **Managed** (AWS Secrets Manager / SSM).

Rules applied:
- Non-sensitive config (hosts, ports, names, URLs, feature flags, model names, TTLs) → **ConfigMap**.
- Passwords, tokens, API keys, JWT secrets, DSNs (embed credentials) → **Secret**.
- Secrets that must not live in the cluster (prod DB creds, API keys rotated externally) → **Managed** (AWS Secrets Manager / SSM), injected via External Secrets Operator or the AWS Secrets Manager CSI driver.

> NOTE: The `.env` currently contains **real secrets in plaintext** (see `ANTHROPIC_API_KEY`). This file documents the target state, not a recommendation to keep them in `.env`. Never commit the real `.env`.

---

## Full key classification

### PostgreSQL (compose `db` → K8s StatefulSet or Amazon RDS)

| .env key | Example / current | Target |
|----------|-------------------|--------|
| `POSTGRES_DB` | `postgres` | ConfigMap |
| `POSTGRES_USER` | `odoo` | ConfigMap |
| `POSTGRES_PASSWORD` | `odoo` | **Secret** |

### Odoo DB connection (read by official entrypoint)

| .env key | Example / current | Target |
|----------|-------------------|--------|
| `ODOO_DB_HOST` | `db` | ConfigMap (→ RDS endpoint in prod) |
| `ODOO_DB_PORT` | `5432` | ConfigMap |
| `ODOO_DB_USER` | `odoo` | ConfigMap |
| `ODOO_DB_PASSWORD` | `odoo` | **Secret** |

### Public domain / base URL

| .env key | Example / current | Target |
|----------|-------------------|--------|
| `DOMAIN` | `cloud-ai-erp.duckdns.org` | ConfigMap |
| `URL` | `https://cloud-ai-erp.duckdns.org/` | ConfigMap |

### Anthropic Claude (shared by odoo + invoice-ai/worker)

| .env key | Example / current | Target |
|----------|-------------------|--------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | **Secret** (recommend **Managed** via Secrets Manager; rotate externally) |

### invoice-ai (INVOICE_AI_* prefix)

| .env key | Example / current | Target |
|----------|-------------------|--------|
| `INVOICE_AI_JWT_SECRET` | `invoice-agent-dev-secret-...` | **Secret** (must match Odoo `invoice_agent.jwt_secret`) |
| `INVOICE_AI_JWT_AUDIENCE` | `invoice-ai` | ConfigMap |
| `INVOICE_AI_JWT_TTL_SECONDS` | `60` | ConfigMap |
| `INVOICE_AI_VOYAGE_API_KEY` | *(empty)* | **Secret** (recommend **Managed**) |
| `INVOICE_AI_VOYAGE_MODEL` | `voyage-3` | ConfigMap |
| `INVOICE_AI_VOYAGE_DIMENSIONS` | `1024` | ConfigMap |
| `INVOICE_AI_RERANK_MODEL` | `rerank-2.5` | ConfigMap |
| `INVOICE_AI_DATABASE_URL` | *(empty, `postgresql://user:pass@host/db`)* | **Secret** (DSN embeds credentials) |
| `INVOICE_AI_ANTHROPIC_MODEL` | `claude-opus-4-8` | ConfigMap |
| `INVOICE_AI_ANTHROPIC_MAX_TOKENS` | `2048` | ConfigMap |
| `INVOICE_AI_ANTHROPIC_TIMEOUT_SECONDS` | `90.0` | ConfigMap |
| `INVOICE_AI_ANTHROPIC_MAX_RETRIES` | `2` | ConfigMap |
| `INVOICE_AI_BUILD_SHA` | `dev` | ConfigMap |

### RabbitMQ (broker)

| .env key | Example / current | Target |
|----------|-------------------|--------|
| `RABBITMQ_HOST` | `rabbitmq` | ConfigMap |
| `RABBITMQ_PORT` | `5672` | ConfigMap |
| `RABBITMQ_DEFAULT_USER` | `invoice_agent` | ConfigMap |
| `RABBITMQ_DEFAULT_PASS` | `invoice_agent` | **Secret** |

### Redis (LLM cache + session store)

| .env key | Example / current | Target |
|----------|-------------------|--------|
| `REDIS_URL` | `redis://redis:6379/0` | ConfigMap (→ **Secret** if it ever embeds a password) |
| `LLM_CACHE_TTL_HOURS` | `168` | ConfigMap |
| `ODOO_SESSION_REDIS_PREFIX` | `odoo-session:` | ConfigMap |
| `ODOO_SESSION_REDIS_TTL_DAYS` | `7` | ConfigMap |

### AWS / S3 (attachments + backups)

| .env key | Example / current | Target |
|----------|-------------------|--------|
| `S3_ATTACHMENTS_BUCKET` | *(empty)* | ConfigMap |
| `S3_BACKUP_BUCKET` | *(empty)* | ConfigMap |
| `RETENTION_DAYS` | `30` | ConfigMap |

### RDS migration (infra/scripts/db-migrate.sh)

| .env key | Example / current | Target |
|----------|-------------------|--------|
| `RDS_HOST` | *(empty, → RDS endpoint)* | ConfigMap |
| `RDS_PORT` | `5432` | ConfigMap |
| `RDS_DB` | `odoo` | ConfigMap |
| `RDS_USER` | `odoo_admin` | ConfigMap |
| `RDS_PASSWORD` | *(empty)* | **Secret** (recommend **Managed** — lives in Secrets Manager) |
| `RDS_SECRET_NAME` | `odoo-invoice-agent-production/rds/master-password` | ConfigMap (the *name* is not sensitive) |
| `RDS_SECRET_REGION` | `eu-west-1` | ConfigMap |

### Locust load testing (invoice-ai/locustfile.py)

| .env key | Example / current | Target |
|----------|-------------------|--------|
| `LOCUST_INVOICE_AI_URL` | `http://localhost:8100` | ConfigMap |
| `LOCUST_ODOO_URL` | `http://localhost:8069` | ConfigMap |
| `LOCUST_JWT_SECRET` | *(empty, must equal INVOICE_AI_JWT_SECRET)* | **Secret** |
| `LOCUST_PDF_DIR` | `invoice-ai/tests/fixtures` | ConfigMap |
| `LOCUST_EXTRACTION_TIMEOUT` | `60` | ConfigMap |
| `LOCUST_ODOO_DB` | `odoo` | ConfigMap |
| `LOCUST_ODOO_USER` | `admin` | ConfigMap |
| `LOCUST_ODOO_PASSWORD` | `admin` | **Secret** (recommend **Managed** in prod) |

### Deployment scripts (scripts/cutover.sh)

| .env key | Example / current | Target |
|----------|-------------------|--------|
| `DRY_RUN` | `0` | ConfigMap |
| `COMPOSE_FILE` | `docker-compose.yml` | ConfigMap |
| `HEALTH_TIMEOUT` | `120` | ConfigMap |
| `ROLLBACK_WINDOW` | `240` | ConfigMap |

---

## Where each class goes

### ConfigMaps
All non-sensitive: DB name/user/host/port, domain/URL, feature flags, model names, dimensions, TTLs, bucket names, retention, RDS endpoint + region + secret *name*, locust URLs/DB/user, deployment-script vars, build SHA.

Representative ConfigMap:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: odoo-config
data:
  ODOO_DB_HOST: "postgres"          # -> RDS endpoint in prod
  ODOO_DB_PORT: "5432"
  ODOO_DB_USER: "odoo"
  POSTGRES_DB: "postgres"
  POSTGRES_USER: "odoo"
  DOMAIN: "cloud-ai-erp.duckdns.org"
  URL: "https://cloud-ai-erp.duckdns.org/"
  INVOICE_AI_JWT_AUDIENCE: "invoice-ai"
  INVOICE_AI_JWT_TTL_SECONDS: "60"
  INVOICE_AI_VOYAGE_MODEL: "voyage-3"
  INVOICE_AI_VOYAGE_DIMENSIONS: "1024"
  INVOICE_AI_RERANK_MODEL: "rerank-2.5"
  INVOICE_AI_ANTHROPIC_MODEL: "claude-opus-4-8"
  INVOICE_AI_ANTHROPIC_MAX_TOKENS: "2048"
  INVOICE_AI_ANTHROPIC_TIMEOUT_SECONDS: "90.0"
  INVOICE_AI_ANTHROPIC_MAX_RETRIES: "2"
  INVOICE_AI_BUILD_SHA: "dev"
  RABBITMQ_HOST: "rabbitmq"
  RABBITMQ_PORT: "5672"
  RABBITMQ_DEFAULT_USER: "invoice_agent"
  REDIS_URL: "redis://redis:6379/0"
  LLM_CACHE_TTL_HOURS: "168"
  ODOO_SESSION_REDIS_PREFIX: "odoo-session:"
  ODOO_SESSION_REDIS_TTL_DAYS: "7"
  S3_ATTACHMENTS_BUCKET: ""
  S3_BACKUP_BUCKET: ""
  RETENTION_DAYS: "30"
  RDS_HOST: ""
  RDS_PORT: "5432"
  RDS_DB: "odoo"
  RDS_USER: "odoo_admin"
  RDS_SECRET_NAME: "odoo-invoice-agent-production/rds/master-password"
  RDS_SECRET_REGION: "eu-west-1"
  LOCUST_INVOICE_AI_URL: "http://localhost:8100"
  LOCUST_ODOO_URL: "http://localhost:8069"
  LOCUST_PDF_DIR: "invoice-ai/tests/fixtures"
  LOCUST_EXTRACTION_TIMEOUT: "60"
  LOCUST_ODOO_DB: "odoo"
  LOCUST_ODOO_USER: "admin"
  DRY_RUN: "0"
  COMPOSE_FILE: "docker-compose.yml"
  HEALTH_TIMEOUT: "120"
  ROLLBACK_WINDOW: "240"
```

### Secrets
All sensitive: passwords, API keys, JWT secrets, DSNs, locust admin password.

Representative Secret:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: odoo-secrets
type: Opaque
stringData:
  POSTGRES_PASSWORD: ""          # fill from vault, never commit
  ODOO_DB_PASSWORD: ""
  ANTHROPIC_API_KEY: ""
  INVOICE_AI_JWT_SECRET: ""
  INVOICE_AI_VOYAGE_API_KEY: ""
  INVOICE_AI_DATABASE_URL: ""
  RABBITMQ_DEFAULT_PASS: ""
  RDS_PASSWORD: ""
  LOCUST_JWT_SECRET: ""
  LOCUST_ODOO_PASSWORD: ""
```

### Managed (AWS Secrets Manager / SSM)
Recommendation for prod — put these in **AWS Secrets Manager** (or SSM Parameter Store, `SecureString`) and inject via **External Secrets Operator** or the **AWS Secrets Manager CSI driver**:
- `ANTHROPIC_API_KEY`
- `INVOICE_AI_VOYAGE_API_KEY`
- `INVOICE_AI_DATABASE_URL` (RDS DSN)
- `RDS_PASSWORD` (and Odoo's `ODOO_DB_PASSWORD`/`POSTGRES_PASSWORD` if RDS is the DB)
- `LOCUST_ODOO_PASSWORD` (only if load-testing against prod)

The `RDS_SECRET_NAME` + `RDS_SECRET_REGION` already hint at this: `odoo-invoice-agent-production/rds/master-password` in `eu-west-1`.

---

## Migration steps
1. Create a `ConfigMap` for every non-sensitive key above (e.g. `odoo-config`).
2. Create a `Secret` for every sensitive key above, sourced from vault/SSM at apply time (never commit literal values).
3. Move prod-sensitive values to **AWS Secrets Manager**; wire an External Secret to sync them into the cluster `Secret`.
4. Update Pod/Deployment env specs to reference the ConfigMap via `envFrom.configMapRef` and the Secret via `valueFrom.secretKeyRef` (or `envFrom.secretRef` for the whole Secret).
5. Delete the real `.env` from any committed location; keep only `.env.example` with placeholder values.
