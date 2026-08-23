# Architecture — Invoice Agent on AWS

> **Last updated:** 2026-08-19
> **Status:** IaC-managed VPC + RDS on private subnets behind ALB, S3 for attachments/backups, Redis for sessions/cache

---

## 1. Network Topology (Two-AZ VPC)

```
                            Internet
                               │
                          ┌────┴────┐
                          │   IGW   │
                          └────┬────┘
                               │
┌──────────────────────────────┼──────────────────────────────┐
│  VPC 10.20.0.0/16           │                              │
│                              │                              │
│  ┌───────────────────┐ ┌────┴────┐ ┌───────────────────┐  │
│  │ PUBLIC-A           │ │         │ │ PUBLIC-B           │  │
│  │ 10.20.0.0/24      │ │  NAT GW │ │ 10.20.1.0/24      │  │
│  │ AZ: eu-west-1a    │ │  (EIP)  │ │ AZ: eu-west-1b    │  │
│  │ ALB, SSM endpoint  │ └────┬────┘ │                    │  │
│  └───────────────────┘       │      └───────────────────┘  │
│                       RT: 0.0.0.0/0 → NAT                 │
│                              │                              │
│  ┌───────────────────┐       │      ┌───────────────────┐  │
│  │ APP-A              │      │      │ APP-B              │  │
│  │ 10.20.10.0/24     │◄─────┘      │ 10.20.11.0/24     │  │
│  │ AZ: eu-west-1a    │             │ AZ: eu-west-1b    │  │
│  │ Odoo EC2 (no pubIP)│            │ (standby)          │  │
│  └────────┬──────────┘             └────────┬──────────┘  │
│           │  5432 (SG: only from app SG)    │              │
│  ┌────────┴─────────────────────────────────┴──────────┐  │
│  │                                                      │  │
│  │  ┌───────────────────┐     ┌───────────────────┐    │  │
│  │  │ DATA-A             │     │ DATA-B             │    │  │
│  │  │ 10.20.20.0/24     │     │ 10.20.21.0/24     │    │  │
│  │  │ AZ: eu-west-1a    │     │ AZ: eu-west-1b    │    │  │
│  │  │ RDS Primary        │     │ RDS Standby        │    │  │
│  │  │ (no internet route)│     │ (no internet route)│    │  │
│  │  └───────────────────┘     └───────────────────┘    │  │
│  │                                                      │  │
│  │  ┌───────────────────┐     ┌───────────────────┐    │  │
│  │  │ REDIS-A            │     │ REDIS-B            │    │  │
│  │  │ 10.20.20.0/24     │     │ 10.20.21.0/24     │    │  │
│  │  │ AZ: eu-west-1a    │     │ AZ: eu-west-1b    │    │  │
│  │  │ ElastiCache Primary│     │ ElastiCache Replica│    │  │
│  │  │ (no internet route)│     │ (no internet route)│    │  │
│  │  └───────────────────┘     └───────────────────┘    │  │
│  │                                                      │  │
│  │  RT: NO 0.0.0.0/0 route — completely isolated       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  S3 VPC Endpoint (Gateway) — attached to all 3 route tables │
└──────────────────────────────────────────────────────────────┘
```

## 2. Security Group Matrix

| Security Group | Inbound | Outbound |
|----------------|---------|----------|
| **ALB SG** | 80/443 from `0.0.0.0/0` | 8069 to App SG only |
| **App SG** | 8069 from ALB SG only | 5432 to Data SG, 6379 to Redis SG, 443/80/53 to internet (NAT) |
| **Data SG** | 5432 from App SG only | None (default egress revoked) |
| **Redis SG** | 6379 from App SG only | 6379 within VPC (replication) |

### Traffic Flow

```
Internet → ALB (443) → Odoo (8069) → RDS (5432)
                                        ↑
                                   Data SG: app-sg ONLY
                                   Route Table: NO internet

Odoo (8069) → ElastiCache (6379) → Redis replication
                ↑
           Redis SG: app-sg ONLY
           Route Table: NO internet
```

## 3. Subnet Tiering

| Tier | CIDR | Purpose | Internet Access |
|------|------|---------|-----------------|
| Public | `10.20.0.0/24`, `10.20.1.0/24` | ALB, NAT Gateway, SSM | IGW (inbound + outbound) |
| App | `10.20.10.0/24`, `10.20.11.0/24` | Odoo EC2, worker containers | NAT only (outbound) |
| Data | `10.20.20.0/24`, `10.20.21.0/24` | RDS PostgreSQL, ElastiCache Redis | **None** |

## 4. RDS Configuration

| Property | Value |
|----------|-------|
| Engine | PostgreSQL 16.4 |
| Instance | db.t4g.medium (2 vCPU, 8 GB RAM) |
| Multi-AZ | Yes (synchronous standby) |
| Storage | 50 GB gp3, auto-scaling to 200 GB |
| Encryption | Enabled (AWS KMS) |
| Backup retention | 7 days with PITR |
| Performance Insights | Enabled (7-day free tier) |
| Enhanced monitoring | 60s interval |
| Parameter group | Custom: shared_buffers=4GB, work_mem=64MB, max_connections=200 |
| Force SSL | Yes |
| Deletion protection | Yes |

### Parameter Group Tuning

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `shared_buffers` | 4 GB | 50% of 8 GB RAM for PostgreSQL buffer cache |
| `effective_cache_size` | 12 GB | Includes OS page cache for planner |
| `work_mem` | 64 MB | Complex invoice/report queries need generous work_mem |
| `maintenance_work_mem` | 1 GB | VACUUM and index creation speed |
| `max_connections` | 200 | Odoo workers × pool_size + headroom |
| `log_min_duration_statement` | 200 ms | Log slow queries for tuning |

## 5. ElastiCache Redis Configuration

| Property | Value |
|----------|-------|
| Engine | Redis 7.1 |
| Instance | cache.t4g.medium |
| Replication | 1 primary + 1 replica (Multi-AZ failover) |
| Encryption | At-rest (KMS) + in-transit (TLS) |
| AUTH | Token stored in Secrets Manager |
| Parameter group | maxmemory-policy: volatile-ttl |
| Maintenance window | Tue 04:00-05:00 UTC |
| Snapshot window | 03:00-04:00 UTC |
| Snapshot retention | 7 days |
| Port | 6379 (SG: app tier only) |

### Redis Usage

| Key Prefix | Purpose | TTL | Consumer |
|------------|---------|-----|----------|
| `odoo-session:` | Odoo HTTP sessions | 7 days | Odoo web workers |
| `llm-cache:` | Claude extraction results | 7 days | invoice-ai worker |

## 6. S3 Buckets

| Bucket | Purpose | Lifecycle | Encryption |
|--------|---------|-----------|------------|
| `${prefix}-attachments` | Odoo filestore (documents, invoices, images) | Standard → Glacier Deep Archive (365 days) | SSE-KMS |
| `${prefix}-backups` | Nightly pg_dump + filestore tarballs | Standard-IA (30d) → Glacier (90d) → Expire (10 years) | SSE-KMS |
| `${prefix}-logs` | Application logs and audit trail | Standard-IA (30d) → Glacier (180d) → Expire (2 years) | SSE-KMS |

### S3 Security

- **Block Public Access**: All four flags enabled on all buckets
- **Bucket Key**: Enabled (reduces KMS API costs by ~99%)
- **Versioning**: Enabled for soft-delete recovery
- **KMS Key**: Shared across all buckets with automatic annual rotation

### S3 Access (EC2 Instance Profile)

| Resource | Actions | Rationale |
|----------|---------|-----------|
| Attachments bucket | GetObject, PutObject, DeleteObject, ListBucket | Full filestore CRUD |
| Backups bucket | PutObject, ListBucket | Write-only (backup push) |
| Logs bucket | PutObject | Write-only (audit trail) |
| KMS key | Decrypt, GenerateDataKey | SSE-KMS operations |

## 7. Secrets Management

| Secret | Storage | Access |
|--------|---------|--------|
| RDS master password | AWS Secrets Manager | Terraform + migration script |
| Odoo DB password | AWS Secrets Manager | EC2 instance IAM role |
| Redis AUTH token | AWS Secrets Manager | EC2 instance IAM role |
| Docker/Compose secrets | `.env` file on EC2 | Not in git, manual only |
| GitHub Actions secrets | GitHub repo settings | CI/CD pipeline |

## 8. Service Stack (Post-Migration)

```
EC2 (App Subnet)           Data Subnet (Isolated)
┌─────────────────────┐    ┌─────────────────────┐
│  Docker Compose:    │    │                     │
│  ┌──────┐           │    │  ┌──────────────┐   │
│  │ Odoo │ ──────────│────│──│ RDS Postgres │   │
│  │:8069 │           │5432│  │ :5432         │   │
│  └──────┘           │    │  │ Multi-AZ      │   │
│  ┌──────┐           │    │  └──────────────┘   │
│  │Workr │           │    │                     │
│  └──────┘           │    │  ┌──────────────┐   │
│  ┌──────┐           │    │  │ Redis 7.1    │   │
│  │Rabbit│           │    │  │ :6379         │   │
│  │ MQ   │           │    │  │ Multi-AZ      │   │
│  └──────┘           │    │  └──────────────┘   │
│  ┌──────┐           │    │                     │
│  │InvoiceAI│        │    └─────────────────────┘
│  └──────┘           │
│  ┌──────┐           │
│  │Nginx │           │
│  │:80/443│          │
│  └──────┘           │
└─────────────────────┘
        │
   ALB (Public Subnet)
        │
   Internet (443)
```

### Data Flow

```
Invoice PDF → Odoo (OCR) → RabbitMQ → invoice-ai (Claude)
                                          │
                                    Redis cache check
                                    (hit? → skip Claude)
                                          │
                                    Result → RabbitMQ
                                          │
                                    Odoo ← JWT-signed result
                                          │
                                    Store in S3 (filestore)
```

## 9. File Layout

```
├── infra/
│   ├── terraform/              # IaC for VPC + RDS + S3 + Redis
│   │   ├── main.tf             # Provider, backend
│   │   ├── variables.tf        # Input variables
│   │   ├── vpc.tf              # VPC, IGW, EIP
│   │   ├── subnets.tf          # 6 subnets + NAT + S3 endpoint
│   │   ├── routes.tf           # 3 route tables (pub/app/data)
│   │   ├── security_groups.tf  # Tiered SGs (alb/app/data/redis)
│   │   ├── rds.tf              # Multi-AZ RDS + Secrets + Alarms
│   │   ├── s3.tf               # 3 S3 buckets + KMS + lifecycle
│   │   ├── iam.tf              # EC2 instance profile + policies
│   │   ├── elasticache.tf      # Redis 7.1 replication group
│   │   └── outputs.tf          # Exported values
│   ├── scripts/
│   │   └── db-migrate.sh       # Dump/restore from local to RDS
│   └── observability/          # Prometheus + Grafana stack (v0.11)
│       ├── docker-compose.observability.yml
│       ├── prometheus/
│       │   ├── prometheus.yml    # Scrape configs (5 targets)
│       │   └── alert_rules.yml   # 7 alerting + 10 recording rules
│       ├── alertmanager/
│       │   └── alertmanager.yml  # Slack / email routing
│       └── grafana/
│           ├── provisioning/
│           │   ├── datasources/prometheus.yml
│           │   └── dashboards/dashboard.yml
│           └── dashboards/
│               └── agent-slo.json  # SLO dashboard as code
├── custom_addons/
│   ├── s3_storage/             # S3 filestore override addon
│   │   ├── models/ir_attachment.py
│   │   └── views/res_config_settings_views.xml
│   ├── session_redis/          # Redis session store addon
│   │   ├── session_store.py
│   │   └── hooks.py
│   └── invoice_agent/          # Main invoice agent addon
├── invoice-ai/
│   └── app/
│       ├── consumer.py         # RabbitMQ worker (with LLM cache)
│       ├── llm_cache.py        # Redis-backed extraction cache
│       └── ...
├── scripts/
│   ├── backup.sh               # Local backup (dev)
│   ├── odoo-backup-s3.sh       # S3 backup (production)
│   ├── sync-filestore-to-s3.sh # Initial filestore migration
│   ├── odoo-backup.service     # systemd unit
│   └── odoo-backup.timer       # Nightly trigger
├── docker-compose.yml          # Full local/dev stack
├── docker-compose.prod.yml     # Production overlay (GHCR image)
├── docker-compose.prod.rds.yml # RDS overlay (removes local postgres)
└── docs/
    ├── architecture.md         # This file
    └── runbooks/
        └── db-migration.md     # Step-by-step migration runbook
```

## 10. Backup Strategy

| Component | Method | Frequency | Retention | Storage |
|-----------|--------|-----------|-----------|---------|
| PostgreSQL | pg_dump -Fc | Daily 03:00 UTC | 30 days local, 10 years S3 | S3 backups bucket |
| Filestore | tar.gz | Daily 03:00 UTC | 30 days local, 10 years S3 | S3 backups bucket |
| Odoo sessions | Redis TTL | Automatic | 7 days | ElastiCache |
| LLM cache | Redis TTL | Automatic | 7 days | ElastiCache |
| S3 attachments | Versioning + lifecycle | Continuous | Glacier Deep Archive after 365d | S3 attachments bucket |

### Backup S3 Structure

```
s3://<backups-bucket>/
└── daily/
    └── 20260101/
        ├── invoice_agent.dump          # pg_dump custom format
        └── invoice_agent-filestore.tar.gz  # filestore tarball
```

## 11. CI/CD Integration

The GitHub Actions workflow now includes Terraform validation:

```yaml
# .github/workflows/ci.yml additions:
terraform-fmt:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: hashicorp/setup-terraform@v3
    - run: terraform fmt -check -recursive infra/terraform/

terraform-validate:
  runs-on: ubuntu-latest
  needs: terraform-fmt
  steps:
    - uses: actions/checkout@v4
    - uses: hashicorp/setup-terraform@v3
    - run: terraform init -backend=false infra/terraform/
    - run: terraform validate -chdir=infra/terraform/
```

## 12. Environment Variables

### Docker Compose Services

| Service | Variable | Default | Purpose |
|---------|----------|---------|---------|
| Odoo | `REDIS_URL` | `redis://localhost:6379/0` | Redis connection for sessions |
| Odoo | `ODOO_SESSION_REDIS_PREFIX` | `odoo-session:` | Session key prefix |
| Odoo | `ODOO_SESSION_REDIS_TTL_DAYS` | `7` | Session TTL |
| invoice-ai | `REDIS_URL` | `redis://localhost:6379/0` | Redis connection for LLM cache |
| invoice-ai | `LLM_CACHE_TTL_HOURS` | `168` | Cache TTL (7 days) |
| worker | `REDIS_URL` | `redis://localhost:6379/0` | Redis connection for LLM cache |
| worker | `LLM_CACHE_TTL_HOURS` | `168` | Cache TTL (7 days) |

### Production Environment (.env)

```bash
# Redis (from Terraform output)
REDIS_URL=redis://:AUTH_TOKEN@<redis-endpoint>:6379/0

# S3 (from Terraform output)
S3_ATTACHMENTS_BUCKET=<prefix>-attachments
S3_BACKUPS_BUCKET=<prefix>-backups
S3_LOGS_BUCKET=<prefix>-logs
```

## 13. Monitoring & Observability

### Prometheus / Grafana Stack (v0.11)

The observability stack runs as a separate Docker Compose file
(`docker-compose.observability.yml`) on a private `monitoring` network.
All services are internal-only except Grafana (port 3000, restricted to
admin access).

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **Prometheus** | prom/prometheus:v2.53.0 | 9090 | Metrics collection (pull model) |
| **Grafana** | grafana/grafana:11.1.0 | 3000 | Dashboard & visualization |
| **Node Exporter** | prom/node-exporter:v1.8.1 | 9100 | Host metrics (USE method) |
| **Postgres Exporter** | prometheuscommunity/postgres-exporter:v0.15.0 | 9187 | RDS metrics |
| **Redis Exporter** | oliver006/redis_exporter:v1.61.0 | 9121 | ElastiCache metrics |
| **Alertmanager** | prom/alertmanager:v0.27.0 | 9093 | Alert routing to Slack/email |

### Application Metrics (invoice-ai)

The FastAPI service exposes `/metrics` (prometheus_client) with:

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `http_requests_total` | Counter | method, endpoint, status | RED: request rate |
| `http_request_duration_seconds` | Histogram | method, endpoint, status | RED: latency |
| `invoice_ocr_duration_seconds` | Histogram | — | OCR processing time |
| `invoice_claude_api_duration_seconds` | Histogram | model | Claude API latency |
| `invoice_claude_tokens_total` | Counter | model, type | Token consumption (cost tracking) |
| `invoice_worker_jobs_total` | Counter | status | Job throughput (done/failed/dead-lettered) |
| `invoice_worker_job_duration_seconds` | Histogram | — | End-to-end job duration |
| `invoice_rabbitmq_queue_depth` | Gauge | queue | Pipeline backlog |

### RED Method (FastAPI Service)

- **R**ate: `rate(http_requests_total[5m])`
- **E**rrors: `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])`
- **D**uration: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`

### USE Method (EC2 Host — via node_exporter)

- **U**tilization: CPU%, memory%, disk%
- **S**aturation: load average, swap usage
- **E**rrors: disk I/O errors, network packet drops

### Alert Rules

| Alert | Condition | Severity | Runbook |
|-------|-----------|----------|---------|
| PipelineErrorRateHigh | Error rate > 2% for 5m | Critical | [pipeline-error-rate.md](runbooks/pipeline-error-rate.md) |
| RDSConnectionsNearCap | Connections > 85% of max for 10m | Warning | [rds-connections.md](runbooks/rds-connections.md) |
| PipelineLatencyHigh | p95 latency > 60s for 5m | Warning | — |
| RedisMemoryHigh | Memory > 80% for 10m | Warning | — |
| NodeCPUHigh | CPU > 85% for 10m | Warning | — |
| NodeDiskSpaceLow | Disk free < 10% for 5m | Critical | — |
| WorkerQueueBacklog | Queue depth > 50 for 5m | Warning | — |

### SLO Dashboard

The Grafana dashboard (`infra/observability/grafana/dashboards/agent-slo.json`)
is provisioned as code and shows:

1. **SLO Overview**: Error rate, invoices/hour, p95 latency, daily token cost
2. **Pipeline RED**: Request rate, error rate, p95 duration by endpoint
3. **Pipeline Breakdown**: OCR duration, Claude API latency, token consumption
4. **Worker & Queue**: Job status, job duration, RabbitMQ queue depth
5. **Infrastructure USE**: CPU, memory, disk on the EC2 host
6. **Database & Redis**: PostgreSQL connections, cache hit ratio, Redis memory

### Key Redis Metrics to Monitor

- **Cache hit ratio**: `Hits / (Hits + Misses)` — should be > 80% for LLM cache
- **Memory usage**: Stay below 80% of allocated
- **Connections**: Monitor for connection pool exhaustion
- **Evictions**: Should be 0 (volatile-ttl policy evicts only expired keys)
