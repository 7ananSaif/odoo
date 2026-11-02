# Invoice Agent — AI-Powered Vendor Invoice Extraction

> **OCR → Claude structured extraction → RAG validation → draft `account.move`**

An Odoo 19 addon that automates vendor invoice data entry. Upload a scanned PDF and the pipeline extracts structured fields (vendor, dates, line items, amounts) using Tesseract OCR + Claude AI, validates the result against the vendor's posting history via pgvector RAG, and produces a draft bill routed by confidence score — no manual typing required.

![License: LGPL-3](https://img.shields.io/badge/license-LGPL--3-blue.svg)

## Architecture

```mermaid
sequenceDiagram
    participant User
    participant Odoo
    participant RabbitMQ
    participant InvoiceAI
    participant Claude
    participant Redis
    participant PGVector

    User->>Odoo: Upload invoice PDF
    Odoo->>Odoo: OCR (Tesseract) + create draft bill
    Odoo->>RabbitMQ: publish extract.request
    RabbitMQ->>InvoiceAI: deliver to worker
    InvoiceAI->>Redis: check LLM cache
    alt Cache hit
        InvoiceAI-->>InvoiceAI: use cached result
    else Cache miss
        InvoiceAI->>Claude: extract (structured output)
        Claude-->>InvoiceAI: InvoiceExtraction JSON
        InvoiceAI->>Redis: store in cache
    end
    InvoiceAI->>PGVector: RAG retrieval (vendor history)
    InvoiceAI->>Claude: validate (RAG context)
    Claude-->>InvoiceAI: ValidationVerdict
    InvoiceAI->>RabbitMQ: publish extract.done
    RabbitMQ->>Odoo: deliver signed result
    Odoo->>Odoo: apply extraction + confidence routing
    Odoo-->>User: draft bill ready for review
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Separate FastAPI service** (ADR-003) | LLM round-trips (5-20s) would pin Odoo HTTP workers — measured 33.5× degradation with workers=2 |
| **RabbitMQ + transactional outbox** (ADR-004) | Guarantees no lost jobs even if the broker restarts mid-request |
| **Claude structured output** | Schema-validated extraction eliminates JSON parsing errors |
| **RAG validation** (Phase 2) | Second Claude call with vendor history catches misclassifications before the accountant sees them |
| **Confidence-based routing** | Auto-fill (≥90%), review (≥70%), or human (<70%) — three-tier kanban |

## Quickstart

```bash
# 1. Clone and configure
git clone https://github.com/7ananSaif/odoo.git
cd odoo
cp .env.example .env   # fill in ANTHROPIC_API_KEY, JWT_SECRET

# 2. Start the stack
docker compose up -d

# 3. Open Odoo (default: admin/admin)
# http://localhost:8069 → Invoicing → Vendors → Bills → Upload

# 4. Upload a scanned invoice PDF
# Watch the extraction status: pending → processing → extracted
# Review the AI-suggested fields in the suggestion panel
```

## How to run this

**Run it locally, on Docker Desktop's Kubernetes. It costs $0 and needs no cloud
account.** The AWS Terraform in this repo is kept for reference only and is not
used — see [the note at the end](#aws-options--not-in-use).

| | `k8s-local/` (default) | `full-infra/` | `lite-infra/` |
|---|---|---|---|
| Runs on | Docker Desktop Kubernetes / kind | EKS | one Lightsail box |
| Database | Postgres StatefulSet + PVC | RDS | Postgres container |
| Cost | **$0** | $$$ (EKS + ALB + NAT + RDS) | ≈$5.10/month |
| Status | **in use** | not in use | not in use |

### `k8s-local` — the free local cluster (Docker Desktop or kind)

The **whole application** — Odoo, Postgres+pgvector, RabbitMQ, Redis, the
`invoice-ai` FastAPI service and its extraction worker — on your machine, with
real PersistentVolumes so the database survives restarts. No cloud account, no
bill. Only the multi-tenant `saas-manager` control plane is left out.

```bash
# 0. Prerequisites: Docker Desktop with Kubernetes enabled, kubectl.
#    (or: kind installed, and use CLUSTER=kind below)

# 1. Build the image and check the cluster
cd k8s-local
make k8s-up                 # no make? bash ../deploy/local-k8s.sh up

# 2. Apply, wait for Postgres, initialise the schema, wait for Odoo
make k8s-deploy             # bash ../deploy/local-k8s.sh deploy

# 3. Open it
#    Docker Desktop: http://localhost:30080
#    kind:           http://localhost:8081
#    either:         kubectl port-forward -n odoo-local svc/odoo 8069:8069

# 4. Day-to-day
make logs         # follow Odoo
make logs-ai      # follow invoice-ai (OCR → Claude → RAG)
make logs-worker  # follow the AMQP extraction worker
make logs-queue   # follow RabbitMQ
make db-shell     # psql
make db-backup    # pg_dump -Fc into ./backups
make k8s-down     # stop, KEEP data
make k8s-destroy  # delete namespace + volumes (asks 'yes')
```

Extraction needs a real Claude key: `ANTHROPIC_API_KEY` in
`k8s-local/base/01-secret.yaml` is an empty placeholder, so the stack runs and
the worker consumes, but each extraction returns 503 and is queued for retry
until you set one (instructions in `k8s-local/README.md` § 0).

```bash
```

On kind, pass the cluster on both commands — `make k8s-up CLUSTER=kind` then
`make k8s-deploy CLUSTER=kind` — or use the script, which takes it as an
argument: `bash deploy/local-k8s.sh up kind`. Full command reference,
data-survival table and troubleshooting:
[`k8s-local/README.md`](k8s-local/README.md).

### Services

| Service | Port | Purpose |
|---------|------|---------|
| Odoo | 8069 (loopback) | ERP + UI + outbox drain |
| invoice-ai | 8100 | FastAPI: OCR → Claude → RAG |
| worker | — | AMQP consumer (Claude calls) |
| RabbitMQ | 15672 (loopback) | Job queue + management UI |
| PostgreSQL | 5434 (loopback) | Database + pgvector |
| Redis | 6379 (loopback) | LLM cache + sessions |
| nginx | 80/443 | Reverse proxy + TLS |

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | (required) | Claude API key |
| `INVOICE_AI_JWT_SECRET` | (required) | Shared JWT secret between Odoo ↔ invoice-ai |
| `REDIS_URL` | `redis://localhost:6379/0` | LLM extraction cache (7-day TTL) |
| `RABBITMQ_HOST` | `rabbitmq` | Job queue broker |
| `POSTGRES_DB` | `postgres` | Database name |
| `POSTGRES_PASSWORD` | `odoo` | Database password |
| `URL` | — | Public base URL for `web.base.url` |

## Load Testing

```bash
# Generate test invoice PDFs
pip install reportlab
python scripts/generate_test_invoices.py --count 10

# Smoke test (5 users, 2 min)
cd invoice-ai
LOCUST_JWT_SECRET=your-secret locust --headless -u 5 -r 1 --run-time 2m

# Full ramp (100 users, 30 min)
LOCUST_JWT_SECRET=your-secret locust --headless -u 100 -r 2 --run-time 30m \
    --csv=results/ramp --html=results/ramp-report.html
```

See [docs/load-test.md](docs/load-test.md) for the capacity report and cost model.

## Cost per Invoice

| Component | Cost per 1,000 invoices |
|-----------|------------------------|
| Claude API (Opus 4, cached) | $71 |
| Claude API (with RAG validation) | $109 |
| Infrastructure (prorated) | $19 |
| **Total (extraction only)** | **$90** |
| **Total (with RAG)** | **$128** |

## Project Structure

```
├── custom_addons/
│   ├── invoice_agent/       # Main Odoo addon (account.move AI fields, outbox, UI)
│   ├── s3_storage/          # S3 filestore override
│   └── session_redis/       # Redis session store
├── invoice-ai/
│   ├── app/
│   │   ├── main.py          # FastAPI service (/v1/extract, /v1/embed, /rag/vendor-context)
│   │   ├── consumer.py      # AMQP worker (Claude calls + RAG validation)
│   │   ├── claude.py        # AsyncAnthropic client with prompt caching
│   │   ├── schemas.py       # InvoiceExtraction Pydantic schema
│   │   ├── validate.py      # RAG validation (account routing + duplicate detection)
│   │   ├── retrieve.py      # Hybrid vector + ref + VAT retrieval (pgvector)
│   │   ├── embeddings.py    # Voyage-3 embedding client
│   │   └── metrics.py       # Prometheus metrics (RED method)
│   ├── locustfile.py        # Load test (Locust)
│   └── pyproject.toml       # Dependencies + tooling
├── k8s-local/               # DEFAULT: Docker Desktop K8s or kind, PV-backed Postgres, $0
│   ├── base/                # kustomize manifests (namespace, deploy, svc, sts, pvc, job)
│   └── Makefile             # k8s-up / k8s-deploy / k8s-down / db-shell / db-backup / logs
├── full-infra/              # NOT IN USE: EKS + RDS (kept for reference, costs money)
│   ├── terraform/           # IaC: VPC, RDS, S3, Redis, security groups
│   ├── helm/odoo-stack/     # the workload
│   ├── eks/                 # eksctl cluster manifest, ALB controller notes
│   └── observability/       # Prometheus + Grafana + Alertmanager
├── lite-infra/              # NOT IN USE: one Lightsail instance, ~$5/month
│   ├── *.tf                 # instance, static IP, firewall, $5 billing alarm
│   ├── docker-compose.lite.yml
│   └── boot.sh.tftpl        # cloud-init: docker + compose + schema init
├── deploy/                  # wrappers: local-k8s.sh, lite-aws.sh
├── infra-v1-backup/         # untouched pre-rename snapshot of ./infra (tag: infra-v1)
├── docs/
│   ├── architecture.md      # Full architecture with network topology
│   ├── load-test.md         # Capacity report
│   └── runbooks/            # Operational runbooks
└── docker-compose.yml       # Local development stack
```

## API Endpoints

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| `POST` | `/v1/extract` | JWT | 10/min | Extract invoice data from PDF/image |
| `POST` | `/v1/embed` | JWT | 30/min | Embed documents with Voyage-3 |
| `POST` | `/rag/vendor-context` | JWT | 20/min | Retrieve vendor history for RAG |
| `GET` | `/healthz` | None | — | Liveness probe (returns build SHA) |
| `GET` | `/metrics` | None | — | Prometheus metrics |

## Monitoring

The Grafana SLO dashboard (`full-infra/observability/grafana/dashboards/agent-slo.json`) shows:

- **Pipeline RED**: request rate, error rate, p95 duration
- **Worker & Queue**: job throughput, queue depth, retry rate
- **Infrastructure USE**: CPU, memory, disk, PostgreSQL connections
- **Cost tracking**: daily token consumption, estimated API spend

Key alerts: `PipelineErrorRateHigh`, `PipelineLatencyHigh`, `RDSConnectionsNearCap`, `WorkerQueueBacklog`

## Honest Limitations

- **Requires Anthropic API key** — costs ~$0.07-0.11 per invoice depending on RAG
- **Tesseract OCR accuracy** depends on scan quality — low-DPI or skewed scans degrade extraction
- **RAG needs ≥5 historical bills** per vendor before validation adds value
- **Single-tenant** — no multi-company isolation yet
- **Claude rate limits** — the RPM cap (100 on Build tier) bounds throughput at ~100 invoices/minute with full caching
- **No real-time streaming** — the extraction result arrives via RabbitMQ polling, not WebSocket

## AWS options — NOT IN USE

Both AWS stacks exist here, are validated, and are **deliberately not deployed**,
because they cost money and the local Kubernetes option above does the same job
for $0.

| Directory | What it would create | Why it is off |
|---|---|---|
| `full-infra/` | EKS + RDS + ALB + NAT Gateway | ~$120+/month |
| `lite-infra/` | one Lightsail `nano` instance + static IP | ~$5.10/month |

Nothing is applied automatically — CI only runs `terraform fmt` and `terraform
validate`, never `apply`. As of the last audit the AWS account holds **no EKS
cluster, no RDS, no NAT Gateway and no load balancer**, and the single
`odoo-agent-server` EC2 instance is **stopped**.

```bash
# restart the stopped box (keeps its disk and data)
aws ec2 start-instances --region eu-north-1 --instance-ids i-0fa36cddb156cc98f

# or stand up the cheap stack from scratch (~$5/month)
cd lite-infra && terraform init && terraform apply

# or the production-shaped one (EKS + RDS)
cd full-infra/terraform && terraform init && terraform plan
```

## License

[LGPL-3](LICENSE) — compatible with Odoo Community addons.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for PR workflow, code style, and testing requirements.
