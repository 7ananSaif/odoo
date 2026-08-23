# Runbook — invoice-ai service

Operating guide for the standalone `invoice-ai` service
(`invoice-ai/`, ADR-003). Covers the release pipeline, manual deploys,
rollback, and tracing a deployed image back to a git revision.

## Architecture in one paragraph

`invoice-ai` is a FastAPI service (`/v1/extract` + `GET /healthz`) that
owns OCR + the Anthropic Claude call so Odoo HTTP workers are never
blocked. It is built, published to GHCR, and deployed **independently**
from Odoo. Odoo reaches it over the compose network by service name with a
JWT. The OpenAPI contract (`docs/openapi.yaml`) is the compatibility lock —
checked on every CI run by `invoice-ai/scripts/check_openapi_drift.py`.

## Pipelines

| Trigger | Workflow | What it does |
|---|---|---|
| PR touching `invoice-ai/**` | `.github/workflows/invoice-ai-ci.yml` (test job) | ruff, mypy, pytest, OpenAPI drift check |
| Push to `main` touching `invoice-ai/**` | same (build-and-push job) | builds and pushes `ghcr.io/7ananSaif/invoice-ai:<sha>` + `:latest` |
| CI completed successfully on `main` | `.github/workflows/invoice-ai-deploy.yml` | SSH to EC2, pull `:<sha>`, `up -d`, 30 s `/healthz` gate, auto-rollback |
| Tag `v*` touching `invoice-ai/**` | `.github/workflows/invoice-ai-release.yml` | pushes `:<tag>` + `:<sha>` + `:latest` |

### Secrets required (repo → Settings → Secrets and variables → Actions)

- `EC2_HOST` — EC2 IP or hostname
- `EC2_USERNAME` — ssh user (e.g. `ubuntu`)
- `SSH_PRIVATE_KEY` — deploy key whose public half is in
  `~/.ssh/authorized_keys`; scope it with `command=` / `no-port-forwarding`
  if you want command-restricted access

## Image tags

`ghcr.io/7ananSaif/invoice-ai`:

| Tag | Meaning | Used by |
|---|---|---|
| `:latest` | last `main` build | manual pulls only |
| `:<commit-sha>` | immutable build of one commit | deploy job + rollback |
| `:<version>` (e.g. `v0.8`) | tagged release | verified milestone deployments |

Each image carries the OCI label `org.opencontainers.image.revision` = git
SHA, and the runtime env `INVOICE_AI_BUILD_SHA` (default `dev` for local
uvicorn).

## Deploying manually

```bash
# on the EC2 host, in /opt/odoo
INVOICE_AI_TAG=<sha-or-latest> docker compose \
  -f docker-compose.yml -f docker-compose.prod.yml pull invoice-ai
INVOICE_AI_TAG=<sha-or-latest> docker compose \
  -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps invoice-ai

# verify
curl -s http://127.0.0.1:8100/healthz
# {"status":"ok","build_sha":"<sha>"}
```

`docker-compose.prod.yml` overlays the dev `build:` with
`image: ghcr.io/.../invoice-ai:${INVOICE_AI_TAG:-latest}` and
`pull_policy: always`, so `up -d` never rebuilds locally.

## How the deploy pipeline deploys

1. `workflow_run` event: CI on `main` finished **successfully**.
2. `checkout` at the CI head SHA, then `appleboy/ssh-action` runs a script
   on EC2.
3. Discover the **currently running** image's revision label
   (`org.opencontainers.image.revision`) → `PREVIOUS_SHA`. This is the
   rollback target — never git HEAD.
4. `docker compose ... pull invoice-ai` with `INVOICE_AI_TAG=<target-sha>`,
   then `up -d`.
5. Health gate: poll `http://127.0.0.1:8100/healthz` every second for 30 s;
   requires HTTP 200 **and** `build_sha == target-sha` (proves we poll the
   right image).
6. On gate failure: redeploy `PREVIOUS_SHA`, re-poll up to 40 s, then
   `exit 1` — the job goes red on `main` on purpose.

## What a red deploy means

- The deploy job failed its health gate and rolled back to the previous
  SHA, **or** the rollback itself failed (exit 2 → manual intervention).
- First action: read the job log step "Deploy over SSH with health gate +
  auto rollback"; look for `!!! DEPLOY FAILED` and the rollback result.
- Second: `curl -s http://127.0.0.1:8100/healthz` on EC2 — the
  `build_sha` tells you which image ended up running.
- The addon inside Odoo degrades to queued retries while the service is
  down (see milestone v0.8 drill), so a failed deploy is survivable —
  fix, push, let the pipeline re-deploy.

## Rolling back manually

```bash
# pick the last-good SHA from the Actions log (PREVIOUS_SHA) or the
# previous container label, then:
INVOICE_AI_TAG=<last-good-sha> docker compose \
  -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps invoice-ai
curl -s http://127.0.0.1:8100/healthz   # verify build_sha
```

Rollback order between the two services (v0.8 agreement):

1. `invoice-ai` first — image swap with health gate; Odoo tolerates it.
2. Odoo second — only if the addon calls a schema the rolled-back service
   doesn't understand (check the OpenAPI diff first).

## Tracing a deployed image to git

```bash
# from the running container
docker inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' \
  $(docker compose ps -q invoice-ai)

# or over HTTP
curl -s http://127.0.0.1:8100/healthz        # build_sha field

# that SHA is the GHCR tag:
docker buildx imagetools inspect ghcr.io/7ananSaif/invoice-ai:<sha>
```

## Local development

```bash
cd invoice-ai
pip install -e ".[dev]"
uvicorn app.main:app --reload          # http://127.0.0.1:8000/docs
pytest -q                              # mocked Claude, no network
ruff check app tests scripts
mypy app/
python scripts/check_openapi_drift.py  # contract lock vs docs/openapi.yaml
