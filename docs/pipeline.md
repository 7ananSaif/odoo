# CI/CD Pipeline Architecture

> **Full trace:** PR → CI (lint + test) → merge to production → deploy (compose rebuild + module upgrade + health check) → HTTPS rollback guarantee.

---

## 1. Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              GITHUB ACTIONS                                          │
│                                                                                      │
│  ┌──────────┐    ┌────────────┐    ┌────────────┐    ┌──────────────────────────┐   │
│  │ Developer │    │  ci.yml    │    │  MERGE to  │    │      deploy.yml          │   │
│  │ opens PR  │───►│            │───►│ production │───►│                          │   │
│  │ (feature) │    │            │    │            │    │  on: push → production   │   │
│  └──────────┘    │ ┌────────┐ │    └─────┬──────┘    └───────────┬──────────────┘   │
│                  │ │  ruff  │ │          │                        │                  │
│                  │ │ check  │ │          │  ┌─────────────────────┘                  │
│                  │ └───┬────┘ │          │  │                                        │
│                  │     ▼      │          │  ▼                                        │
│                  │ ┌────────┐ │    ┌─────────────┐                                   │
│                  │ │  Odoo  │ │    │  SSH into   │                                   │
│                  │ │  tests │ │    │    EC2      │                                   │
│                  │ └────────┘ │    └──────┬──────┘  EC2 INSTANCE                     │
│                  └────────────┘           │                                          │
│                                           ▼                                          │
│                                   ┌──────────────┐   ┌──────────────────────────┐    │
│                                   │ Record PREV  │   │ ⚠️ FAILURE: port 80      │    │
│                                   │ SHA + DB     │   │   closed / DNS wrong     │    │
│                                   │ snapshot     │   └──────────────────────────┘    │
│                                   └──────┬───────┘                                   │
│                                          ▼                                           │
│                                   ┌──────────────┐   ┌──────────────────────────┐    │
│                                   │  git pull    │   │ ⚠️ FAILURE: SSH key      │    │
│                                   │  origin      │   │   expired / host changed │    │
│                                   │  production  │   └──────────────────────────┘    │
│                                   └──────┬───────┘                                   │
│                                          ▼                                           │
│                                   ┌──────────────┐   ┌──────────────────────────┐    │
│                                   │  docker      │   │ ⚠️ FAILURE: disk full    │    │
│                                   │  compose     │   │   / Docker build error   │    │
│                                   │  up -d       │   └──────────────────────────┘    │
│                                   │  --build     │                                   │
│                                   └──────┬───────┘                                   │
│                                          ▼                                           │
│                                   ┌──────────────┐   ┌──────────────────────────┐    │
│                                   │  -u          │   │ ⚠️ FAILURE: module      │    │
│                                   │  invoice_    │   │   upgrade breaks DB     │    │
│                                   │  agent       │   └──────────────────────────┘    │
│                                   └──────┬───────┘                                   │
│                                          ▼                                           │
│                                   ┌──────────────┐                                   │
│                                   │  Restart     │                                   │
│                                   │  Odoo        │                                   │
│                                   └──────┬───────┘                                   │
│                                          ▼                                           │
│                                   ┌──────────────────┐                               │
│                                   │  HTTPS Health    │    ┌─────────────────────┐    │
│                                   │  Check           │    │ ⚠️ FAILURE: nginx  │    │
│                                   │  (poll up to     │───►│   wrong config /   │    │
│                                   │   60s for 200)   │    │   Odoo not started │    │
│                                   └──────┬───────────┘    └─────────┬───────────┘    │
│                                          │                          │                │
│                                    ✅ 200 └──  ❌ NOT 200           │                │
│                                          ▼                          ▼                │
│                                   ┌──────────────┐        ┌──────────────────┐       │
│                                   │ ✅ Done      │        │  ROLLBACK:       │       │
│                                   │ Clean up     │        │  git checkout    │       │
│                                   │ DB snapshot  │        │  prev SHA       │       │
│                                   │ Verbose logs │        │  compose up      │       │
│                                   └──────────────┘        │  verify HEALTH  │       │
│                                                            └──────┬───────────┘      │
│                                                                   │                   │
│                                                          ✅ HTTP 200 └── ❌ still fail │
│                                                                   ▼                   │
│                                                            ┌──────────────────┐       │
│                                                            │ ALERT: Manual   │       │
│                                                            │ intervention    │       │
│                                                            │ required        │       │
│                                                            └──────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Stage-by-Stage Guide

### 2.1 Developer Opens PR

**Before push:**
```bash
git checkout -b feat/add-confidence-filter
# Make changes
git add -A
git commit -m "[IMP] invoice_agent: add Low Confidence filter to queue view"
git push origin feat/add-confidence-filter
```

**Expected outcome:**
- PR created with `feat/*` → `main` or `production`
- `ci.yml` triggers automatically
- Status checks appear in GitHub PR page

### 2.2 CI — `ci.yml`

**Trigger:** `pull_request: [main, production]` and `push: [main, production]`

**Jobs run in sequence:**

```
Job: lint (ruff)
  → Install ruff
  → ruff check .        # Python linting: E, F, W, I (isort)
  → ruff format --check . # Format verification (black-compatible)

     ┌──────────────────────────────────────────────┐
     │ FAILURE: ruff exits non-zero                  │
     │ Log: "E501 line too long (92 > 88 characters)"│
     │ Fix: `ruff check --fix .` or manual edit     │
     └──────────────────────────────────────────────┘
     
     │
     ▼

Job: test (odoo)
  → Start postgres service (GitHub-hosted)
  → pip install -r requirements.txt
  → Install invoice_agent deps
  → pip install -e . (odoo editable)
  → ./odoo-bin -d ci -i invoice_agent --test-enable
    --test-tags /invoice_agent --stop-after-init
  → Check for FAIL/ERROR/CRITICAL in log
  
     ┌──────────────────────────────────────────────┐
     │ FAILURE: Odoo tests fail                      │
     │ Log: "FAIL: TestInvoiceConfidence..."         │
     │ Artifact: odoo-test.log (uploaded on failure) │
     │ Fix: Check test log, fix code, rebase        │
     └──────────────────────────────────────────────┘
```

### 2.3 Merge to Production

**Action:** GitHub PR merge button or:
```bash
git checkout production
git merge feat/add-confidence-filter
git push origin production
```

**Required:** `ci.yml` must be green. Branch protection can enforce this.

### 2.4 Deploy — `deploy.yml`

**Trigger:** `push: [production]`

**Concurrency:** `group: deploy-production` — prevents overlapping deploys.

**Steps:**

```
Step 1: Record state
─────────────────────
PREVIOUS_SHA=$(git rev-parse HEAD)     # → a1b2c3d4
TIMESTAMP=$(date +%Y%m%d_%H%M%S)       # → 20260730_131500
pg_dump -U odoo -Fc /tmp/pre_deploy_20260730_131500.dump

Step 2: Pull + Build
─────────────────────
git pull origin production             # Fast-forward to new commit
docker compose up -d --build           # Rebuild odoo image + restart all containers

Step 3: Module Upgrade
──────────────────────
docker compose exec -T odoo odoo -u invoice_agent --stop-after-init --log-level=warn
# This runs the module's __init__.py, migrations, view updates, data updates

Step 4: Restart Odoo
────────────────────
docker compose restart odoo

Step 5: HTTPS Health Check
───────────────────────────
for i in 1..30:
    curl -s -o /dev/null -w "%{http_code}" \
        https://invoices.<domain>/web/login
    if 200: break
    sleep 2

# PLUS websocket check:
curl -s -o /dev/null -w "%{http_code}" \
    -H "Connection: Upgrade" -H "Upgrade: websocket" \
    https://invoices.<domain>/websocket
# Expect: 101

Step 6: Rollback (if health check fails)
────────────────────────────────────────
git checkout $PREVIOUS_SHA
docker compose up -d --build
docker compose restart odoo
# Re-verify health

Step 7: Cleanup
───────────────
rm /tmp/pre_deploy_*.dump          # Deploy succeeded
# OR:
pg_restore ... /tmp/pre_deploy_*   # Deploy failed, manual recovery
```

### 2.5 Failure Mode Summary

| # | Stage | Error | First Log To Read | Resolution |
|---|-------|-------|------------------|------------|
| 1 | ruff check | `E501 line too long` | CI output → specific file+line | `ruff check --fix .` |
| 2 | ruff format | `would reformat...` | CI output → file list | `ruff format .` |
| 3 | Odoo test | `FAIL: test_xyz` | `odoo-test.log` → `FAILED` line | Fix test or code |
| 4 | Odoo test | `ModuleNotFoundError` | `odoo-test.log` → import traceback | Check `requirements.txt` |
| 5 | SSH deploy | `Host key verification failed` | GitHub Actions log | Update `known_hosts` or SSH key |
| 6 | SSH deploy | `Permission denied (publickey)` | GitHub Actions log | Check `SSH_PRIVATE_KEY` secret |
| 7 | compose build | `no space left on device` | `df -h` on EC2 | `docker system prune -af` |
| 8 | compose build | `failed to solve: ...` | `docker compose build` output | Check Dockerfile syntax |
| 9 | module upgrade | `ERROR: ...` | `docker compose logs odoo` | Fix module code |
| 10 | health check | `HTTP 502` | `docker compose logs nginx` | Check Odoo is running |
| 11 | health check | `HTTP 000` (connection refused) | `docker compose ps` | Check nginx+odoo status |
| 12 | health check | `HTTP 301` (redirect loop) | `curl -v https://...` | Check proxy_mode + X-Forwarded-Proto |
| 13 | websocket check | `HTTP 200` (not 101) | `docker compose logs nginx \| grep /websocket` | Fix nginx `/websocket` location block |
| 14 | rollback | `git checkout` fails | Git output | Check working tree is clean (`git stash`) |
| 15 | cert renewal | ACME 301 redirect | `docker compose logs nginx` | ACME location block missing |

---

## 3. Disaster Recovery — Rebuild From Zero

**Procedure documented in:** [`docs/deployment.md`](deployment.md#11-disaster-recovery--full-rebuild-from-zero)

**Timed recovery test:**
```bash
time sh -c '
    docker compose down -v
    git clone <repo-url> /opt/odoo
    # ... restore DB and filestore ...
    docker compose up -d
    curl -s -o /dev/null -w "%{http_code}" https://invoices.<domain>/web/login
'
# Target: < 30 minutes
```

### What Must Survive Disaster

| Asset | Backup Frequency | Backup Method | Restore Command |
|-------|-----------------|---------------|-----------------|
| PostgreSQL database | Daily | `pg_dump -Fc` → S3 | `pg_restore --clean --if-exists -d odoo file.dump` |
| Filestore (attachments) | Daily | `tar czf` → S3 | `tar xzf file.tar.gz -C /var/lib/odoo/filestore/` |
| Code (git) | Every push | GitHub repo | `git clone` |
| `.env` secrets | Manual (printed once) | Password manager | `cat > .env << EOF...EOF` |
| TLS certificates | Auto-renewed | Certbot + named volume | `certbot certonly --webroot` |

---

## 4. Verification Steps After Deploy

### 4.1 Automated (in CI)

```bash
# HTTPS check
curl -sI https://invoices.<domain> | grep "200 OK"

# HSTS header
curl -sI https://invoices.<domain> | grep -i "strict-transport"

# No mixed content
curl -s https://invoices.<domain>/web/login | grep -c 'http://'
# Expected: 0

# WebSocket upgrade
curl -s -o /dev/null -w "%{http_code}" \
    -H "Connection: Upgrade" -H "Upgrade: websocket" \
    https://invoices.<domain>/websocket
# Expected: 101

# Certificate validity
echo | openssl s_client -connect invoices.<domain>:443 2>/dev/null | \
    openssl x509 -noout -enddate
```

### 4.2 Manual (after deploy)

1. Open `https://invoices.<domain>` in browser
2. Log in — verify session works over HTTPS
3. Open an invoice — verify attachments load
4. Open queue kanban — verify WebSocket connection (DevTools → Network → filter "WS")
5. Test file upload — verify `client_max_body_size` allows invoice PDFs up to 100 MB

---

## 5. Tag v0.4 — Release Checklist

### 5.1 Prerequisites

- [ ] Nginx config deployed and tested (syntax check passes)
- [ ] docker-compose.yml with nginx + certbot services deployed
- [ ] `.env.example` documented and committed
- [ ] SSL Labs grade A+ confirmed (or at least A)
- [ ] `certbot renew --dry-run` passes
- [ ] Websocket verification: `101 Switching Protocols` confirmed
- [ ] Port 8069 confirmed closed from external scan (`nc -vz ... 8069` → fails)
- [ ] HSTS header present (`curl -sI ... | grep -i strict-transport`)
- [ ] Rollback procedure tested (force health check failure, verify rollback)
- [ ] Disaster recovery procedure timed (< 30 min)
- [ ] `CHANGELOG.md` updated for v0.4
- [ ] `docs/deployment.md` committed with all runbook sections

### 5.2 Tag and Release

```bash
# Update CHANGELOG.md:
#   Change "[Unreleased]" to "v0.4 — 2026-07-30"
git add CHANGELOG.md docs/ docs/deployment.md docs/reverse-proxy-analysis.md
git add nginx/conf.d/odoo.conf .env.example
git add docker-compose.yml .github/workflows/deploy.yml

git commit -m "[REL] v0.4 — Nginx reverse proxy, TLS, websockets, auto-deploy over HTTPS"

# Tag
git tag -a v0.4 -m "v0.4 — Auto-deployed over HTTPS with full runbook"

# Verify tag
git tag -l "v0.4"
git show v0.4

# Push
git push origin production
git push origin v0.4
```

### 5.3 Post-Release Verification

```bash
# Deploy triggered? → GitHub Actions
open https://github.com/<org>/odoo/actions

# Live check
curl -sI https://invoices.<domain>

# TLS grade
open https://www.ssllabs.com/ssltest/analyze.html?d=invoices.<domain>

# Renewal test
docker compose run --rm certbot renew --dry-run

# Rollback drill
# Intentionally break a view, push, watch rollback, then fix forward
