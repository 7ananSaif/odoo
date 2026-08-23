# Deployment Runbook — Invoice Agent Odoo on EC2

> **Last updated:** 2026-07-30
> **Target:** `https://invoices.<domain>` serving Odoo 19 via Nginx reverse proxy with Let's Encrypt TLS, websockets enabled, port 8069 closed to the world.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Secrets Inventory](#2-secrets-inventory)
3. [DNS & EC2 Setup](#3-dns--ec2-setup)
4. [Nginx Reverse Proxy](#4-nginx-reverse-proxy)
5. [Let's Encrypt TLS](#5-lets-encrypt-tls)
6. [Proxy Mode & Trusted Headers](#6-proxy-mode--trusted-headers)
7. [Websocket Semantics](#7-websocket-semantics)
8. [CI/CD Pipeline](#8-cicd-pipeline)
9. [Deploy Procedure](#9-deploy-procedure)
10. [Rollback Procedure](#10-rollback-procedure)
11. [Disaster Recovery — Full Rebuild from Zero](#11-disaster-recovery--full-rebuild-from-zero)
12. [TLS Grading & Security Checks](#12-tls-grading--security-checks)
13. [Monitoring & Health Checks](#13-monitoring--health-checks)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Architecture Overview

```
                          Internet
                             │
                        ┌────┴────┐
                        │  Route  │  A record: invoices.<domain> → <Elastic-IP>
                        │  53     │
                        └────┬────┘
                             │
                        ┌────┴────┐
                        │  EC2    │  Security Group: ports 80, 443 open; 8069 CLOSED
                        │  (host) │
                        └────┬────┘
                             │
                   ┌─────────┼─────────┐
                   │         │         │
              ┌────┴──┐ ┌───┴───┐ ┌───┴───┐
              │ Nginx │ │Certbot│ │ Odoo  │  ⋯ upstreams: odoo:8069, odoo:8072
              │:80/443│ │renew  │ │:8069  │
              └────┬──┘ └───────┘ └───┬───┘
                   │                  │
                   │     ┌────────────┤
                   │     │            │
              location /   location /websocket
              ──────────   ─────────────────
              proxy_pass   proxy_pass
              http://      http://
              odoo:8069    odoo:8072
              +headers     +Upgrade +Connection
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Nginx on `:alpine` | 5 MB image, minimal attack surface, no shell in production |
| Certbot in separate container | Keeps renewal lifecycle isolated; nginx restarts via reload |
| Odoo ports bound to `127.0.0.1` only | Defense in depth: even if security group leaks, no external access |
| `proxy_mode = True` via env var | Tells Odoo HTTP stack to trust `X-Forwarded-For` and `X-Forwarded-Proto` |
| Separate `/websocket` location | Required for long-lived WebSocket connections with different timeout/upgrade headers |
| `client_max_body_size 100m` | Scanned invoice PDFs often exceed default 1 MB limit |
| `proxy_read_timeout 720s` | Odoo long-poll and large report generation can exceed default 60s |

### Port Map

| Container | Port | Exposed to Internet | Purpose |
|-----------|------|---------------------|---------|
| nginx | 80 | ✅ (Security Group) | HTTP + ACME HTTP-01 challenge |
| nginx | 443 | ✅ (Security Group) | HTTPS |
| odoo | 8069 | ❌ (127.0.0.1 only) | Odoo HTTP (proxied by nginx) |
| odoo | 8072 | ❌ (127.0.0.1 only) | Odoo longpoll/websocket (proxied by nginx) |
| db | 5432 | ❌ (not mapped) | PostgreSQL — only accessible within Docker network |
| certbot | - | ❌ | Certificate renewal, no ports |

---

## 2. Secrets Inventory

### AWS

| Secret | Location | Managed Via |
|--------|----------|-------------|
| AWS Account ID | AWS Console | IAM |
| Elastic IP | EC2 → Elastic IPs | Terraform / Manual |
| EC2 SSH Key Pair | `~/.ssh/invoice-agent.pem` | AWS Console → Key Pairs |
| Security Group ID | EC2 → Security Groups | Terraform / Manual |

### GitHub Actions

| Secret Name | Value | Used In |
|-------------|-------|---------|
| `EC2_HOST` | Elastic IP or DNS of EC2 | `deploy.yml` |
| `EC2_USERNAME` | `ubuntu` (or `ec2-user` for Amazon Linux) | `deploy.yml` |
| `SSH_PRIVATE_KEY` | Contents of `~/.ssh/invoice-agent.pem` | `deploy.yml` |

### Environment (`.env` file on EC2)

| Variable | Purpose |
|----------|---------|
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `ODOO_DB_HOST` | `db` (Docker service name) |
| `ODOO_DB_PORT` | `5432` |
| `ODOO_DB_USER` | Same as POSTGRES_USER |
| `ODOO_DB_PASSWORD` | Same as POSTGRES_PASSWORD |

> **⚠️ CRITICAL:** The `.env` file must NOT be committed to git. It is created manually once on EC2.

---

## 3. DNS & EC2 Setup

### 3.1 Allocate Elastic IP

```bash
# Via AWS CLI
aws ec2 allocate-address --domain vpc

# Output:
# {
#     "PublicIp": "54.xxx.xxx.xxx",
#     "AllocationId": "eipalloc-xxxxxxxxxxxxx"
# }

# Associate with EC2 instance
aws ec2 associate-address \
    --instance-id i-xxxxxxxxxxxxx \
    --allocation-id eipalloc-xxxxxxxxxxxxx
```

### 3.2 Create A Record (Route 53)

```bash
aws route53 change-resource-record-sets \
    --hosted-zone-id ZXXXXXXXXXXXXXXXXX \
    --change-batch '{
        "Changes": [{
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": "invoices.<domain>",
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [{"Value": "54.xxx.xxx.xxx"}]
            }
        }]
    }'
```

### 3.3 Verify DNS Propagation

```bash
dig +short invoices.<domain>
# → 54.xxx.xxx.xxx   (must match the Elastic IP)
```

### 3.4 Configure Security Group

| Type | Protocol | Port Range | Source | Purpose |
|------|----------|------------|--------|---------|
| SSH | TCP | 22 | `x.x.x.x/32` (your IP) | Admin access |
| HTTP | TCP | 80 | `0.0.0.0/0` | ACME challenge + redirect |
| HTTPS | TCP | 443 | `0.0.0.0/0` | Production traffic |
| Odoo HTTP | TCP | **8069** | **— NONE (CLOSED)** | Blocked to internet |

### 3.5 Verify Ports

```bash
# Before certificate — expect connection refused on 443
nc -vz invoices.<domain> 443
nc -vz invoices.<domain> 80
nc -vz invoices.<domain> 8069     # MUST FAIL (connection refused / timeout)
```

---

## 4. Nginx Reverse Proxy

### 4.1 Configuration (`nginx/conf.d/odoo.conf`)

See full file at [`nginx/conf.d/odoo.conf`](../nginx/conf.d/odoo.conf).

### 4.2 Proxy Headers Explained

```nginx
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
```

| Header | Value | Odoo Usage |
|--------|-------|------------|
| `X-Forwarded-For` | Comma-separated chain of client IPs | Logging, geolocation, access control |
| `X-Forwarded-Proto` | `http` or `https` | Odoo generates correct `https://` URLs in emails and redirects |
| `Host` | Original `Host` header from browser | Virtual hosting, URL generation |
| `X-Real-IP` | Direct client IP (first in chain) | Rate limiting, audit |

### 4.3 ACME HTTP-01 Challenge Location

```nginx
location /.well-known/acme-challenge/ {
    root /var/www/certbot;
    try_files $uri =404;
}
```

**Why this matters:** Let's Encrypt's HTTP-01 challenge proves domain control by:
1. LE generates a random token: `xxxx.yyyy`
2. Certbot writes the token + thumbprint to `/.well-known/acme-challenge/xxxx.yyyy`
3. LE fetches `http://invoices.<domain>/.well-known/acme-challenge/xxxx.yyyy`
4. If the response matches the expected token, domain control is proven

The `location /.well-known/acme-challenge/` block on port 80 serves these requests **before** the `return 301` redirect, so the challenge succeeds even though all other traffic goes to HTTPS.

### 4.4 Testing Nginx Config

```bash
# Syntax check
docker compose exec nginx nginx -t

# Reload after config change
docker compose exec nginx nginx -s reload

# Check logs for errors
docker compose logs nginx
```

---

## 5. Let's Encrypt TLS

### 5.1 First-Time Certificate Issuance

```bash
docker compose run --rm certbot certonly --webroot \
    -w /var/www/certbot \
    -d invoices.<domain>
```

**What happens:**
1. Certbot writes token files to `/var/www/certbot/.well-known/acme-challenge/`
2. Let's Encrypt validates by fetching `http://invoices.<domain>/.well-known/acme-challenge/<token>`
3. On success, certificates are written to `/etc/letsencrypt/live/invoices.<domain>/`
4. These certs are in the `certbot-conf` named volume which nginx also mounts
5. Reload nginx to pick up the new certs: `docker compose exec nginx nginx -s reload`

### 5.2 Certificate Renewal (Automatic)

The `certbot` container runs a loop:
```bash
while true; do
    certbot renew --quiet --webroot -w /var/www/certbot
    nginx -s reload 2>/dev/null || true
    sleep 12h
done
```

**Renewal triggers:** Certbot renews certificates that are within 30 days of expiry.
**Post-renewal:** Nginx is reloaded to pick up the new certificates (zero-downtime).

### 5.3 Manual Renewal Test

```bash
docker compose run --rm certbot renew --dry-run
```

This simulates the renewal process without actually replacing certificates. It proves:
- DNS is still resolving correctly
- Port 80 is accessible
- ACME challenge location is configured properly
- No rate limits have been exceeded

### 5.4 Certificate Paths

| Path | Content | Used By |
|------|---------|---------|
| `/etc/letsencrypt/live/invoices.<domain>/fullchain.pem` | Full certificate chain | nginx `ssl_certificate` |
| `/etc/letsencrypt/live/invoices.<domain>/privkey.pem` | Private key | nginx `ssl_certificate_key` |

### 5.5 HSTS Configuration

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

This tells browsers: "For the next year (31,536,000 seconds), ONLY connect to this domain over HTTPS — never fall back to HTTP." The `includeSubDomains` directive extends this to all subdomains.

**⚠️ Warning:** Once HSTS is observed by a browser, it's enforced for `max-age` seconds. Test with a short `max-age=300` first, then increase.

### 5.6 TLS Compliance Check

```bash
curl -sI https://invoices.<domain> | grep -i strict-transport
# → Strict-Transport-Security: max-age=31536000; includeSubDomains

curl -sI https://invoices.<domain> | grep -i x-forwarded
# (nginx does not echo these back — they're internal to the proxy)

# Check no mixed content
curl -s https://invoices.<domain>/web/login | grep -i 'http://'
# Should return nothing — all assets must load over HTTPS
```

---

## 6. Proxy Mode & Trusted Headers

### 6.1 What `proxy_mode = True` Does

In `odoo/http.py`, when `proxy_mode` is enabled, Odoo's HTTP layer:

1. **Trusts `X-Forwarded-For`** for client IP resolution
   - Without proxy_mode: `request.httprequest.remote_addr` = nginx container IP (e.g., 172.17.0.x)
   - With proxy_mode: `request.httprequest.remote_addr` = real browser IP (e.g., 203.0.113.x)
   
2. **Trusts `X-Forwarded-Proto`** for URL scheme detection
   - Without proxy_mode: Odoo generates `http://` URLs in redirects and emails
   - With proxy_mode: Odoo detects `https://` and generates correct secure URLs

3. **Sets `werkzeug.serving` to False** so werkzeug's own proxy detection doesn't interfere

### 6.2 How Odoo Detects Proxy Mode

```python
# odoo/http.py (simplified)
proxy_mode = odoo.tools.config['proxy_mode']

if proxy_mode:
    # Trust the X-Forwarded-For header for remote_addr
    remote_addr = request.httprequest.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    # Trust X-Forwarded-Proto for scheme
    scheme = request.httprequest.headers.get('X-Forwarded-Proto', 'http')
```

### 6.3 Setting Proxy Mode

**Via environment variable** (our approach — in `docker-compose.yml`):
```yaml
environment:
  PROXY_MODE: "True"
```

**Via `odoo.conf`**:
```ini
[options]
proxy_mode = True
```

The official `odoo:19` image's entrypoint reads `PROXY_MODE` env var and writes it into `odoo.conf` before starting Odoo.

### 6.4 What Happens Without Proxy Mode

| Scenario | Result | Symptom |
|----------|--------|---------|
| `X-Forwarded-For` not trusted | All clients appear as nginx IP | GeoIP shows wrong location, IP-based access rules broken |
| `X-Forwarded-Proto` not trusted | Odoo generates `http://` redirects | Browser shows "not secure" warnings, OAuth redirects fail |
| Websocket without Upgrade headers | Connection hangs | Live chat, queue kanban, bus events don't load |

---

## 7. Websocket Semantics

### 7.1 Why Odoo Uses Websockets

Odoo uses **long-polling / websocket connections** for:
- **Bus / real-time notifications** (`/websocket`) — kanban queue updates, chatter notifications
- **Live chat** (`im_livechat`) — instant messaging
- **Bus connections** — Odoo's internal message bus pushes updates to connected clients

These are served by Odoo's **longpoll** worker on port **8072** (gevent-based).

### 7.2 HTTP Upgrade Handshake

WebSocket connections start as HTTP requests and then **upgrade** to the WebSocket protocol:

```
Client → Server:  GET /websocket HTTP/1.1
                   Host: invoices.<domain>
                   Upgrade: websocket
                   Connection: Upgrade
                   Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
                   Sec-WebSocket-Version: 13

Server → Client:  HTTP/1.1 101 Switching Protocols
                   Upgrade: websocket
                   Connection: Upgrade
                   Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

### 7.3 Critical Nginx Headers for Websocket

```nginx
location /websocket {
    proxy_pass http://odoo_ws_upstream;
    proxy_set_header Upgrade    $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400s;
    proxy_buffering off;
    proxy_request_buffering off;
}
```

| Directive | Why |
|-----------|-----|
| `proxy_set_header Upgrade $http_upgrade` | Passes the client's `Upgrade: websocket` header to the backend |
| `proxy_set_header Connection "upgrade"` | Forces `Connection: upgrade` so the backend knows this is a WebSocket |
| `proxy_read_timeout 86400s` | WebSocket connections can idle for hours without data |
| `proxy_buffering off` | Buffering breaks the streaming nature of WebSocket traffic |

### 7.4 Websocket Failure Modes

| Problem | Symptom | Fix |
|---------|---------|-----|
| Missing `Upgrade` header in nginx | Browser WebSocket `onerror` fires, connection never established | Add `proxy_set_header Upgrade $http_upgrade;` |
| Missing `Connection: upgrade` | WebSocket handshake fails with 400 Bad Request | Add `proxy_set_header Connection "upgrade";` |
| `proxy_read_timeout` too short | WebSocket disconnects after 60s (default) with 504 | Set to `86400s` (24h) or longer |
| Wrong upstream (port 8069 instead of 8072) | Odoo returns 200 but doesn't upgrade | Ensure `/websocket` proxies to `odoo:8072` |

### 7.5 Verifying Websocket Works

```bash
# From the browser console:
var ws = new WebSocket('wss://invoices.<domain>/websocket');
ws.onopen = () => console.log('WebSocket connected');
ws.onerror = (e) => console.error('WebSocket error', e);

# Or via curl to test the HTTP->WS upgrade (limited):
curl -v -H "Connection: Upgrade" -H "Upgrade: websocket" \
    -H "Sec-WebSocket-Version: 13" \
    -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
    https://invoices.<domain>/websocket
# Expect: HTTP/1.1 101 Switching Protocols
```

---

## 8. CI/CD Pipeline

### 8.1 Full Commit-to-Production Path

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              GITHUB ACTIONS                                  │
│                                                                              │
│  PR opened ──► ci.yml ──► merge ──► deploy.yml ──► SSH ──► EC2              │
│                    │                              │           │               │
│               ┌────┴────┐                   ┌─────┴──────┐   │               │
│               │  lint   │                   │  git pull   │   │               │
│               │ (ruff)  │                   │  production │   │               │
│               └────┬────┘                   └─────┬───────┘   │               │
│                    ▼                              ▼            ▼               │
│               ┌──────────┐               ┌──────────────┐                     │
│               │  test    │               │  docker      │                     │
│               │ (odoo    │               │  compose     │                     │
│               │  tests)  │               │  up -d       │                     │
│               └────┬─────┘               │  --build     │     EC2 INSTANCE    │
│                    │                     └──────┬───────┘                     │
│                    ▼                            ▼                             │
│               ┌──────────┐               ┌──────────────┐                     │
│               │  merge   │               │  -u          │                     │
│               │  to main │               │  invoice_    │                     │
│               └──────────┘               │  agent       │                     │
│                                           └──────┬───────┘                     │
│                                                  ▼                             │
│                                           ┌──────────────┐                     │
│                                           │  health      │                     │
│                                           │  check       │                     │
│                                           │  (HTTP 200?) │                     │
│                                           └──────┬───────┘                     │
│                                                  │                             │
│                                          YES     ▼     NO                     │
│                                        ┌────┐        ┌──────┐                 │
│                                        │ ✅ │        │ git  │                 │
│                                        │done│        │check-│                 │
│                                        └────┘        │ out  │                 │
│                                                      │ prev │                 │
│                                                      │ SHA  │                 │
│                                                      └──────┘                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Failure Modes & First Log to Read

| Stage | Failure Mode | First Log to Check |
|-------|-------------|-------------------|
| **lint** | `ruff check` fails | CI output — look for line `E***` or `F***` errors |
| **test** | Odoo test fails | `odoo-test.log` artifact → search for `FAILED` or `TRACEBACK` |
| **merge** | Branch protection blocks | GitHub PR page → "Merge" button disabled, check required checks |
| **git pull** | SSH key expired or host key changed | `docker compose logs deploy` → `Host key verification failed` |
| **compose build** | Docker build fails (no space, bad Dockerfile) | `docker compose build odoo` output → `no space left on device` |
| **module upgrade** | Odoo `-u` fails | `docker compose logs odoo` → `ERROR` or `CRITICAL` |
| **health check** | Odoo returns non-200 | GitHub Actions deploy log → `curl -s -o /dev/null -w "%{http_code}"` |
| **rollback** | Previous SHA also broken | `git log` to find working SHA, manual recovery |

### 8.3 Deploy Trigger

```yaml
on:
  push:
    branches: [production]
```

The pipeline in [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml):
1. **CI gate**: Runs lint + tests on the merge commit
2. **SSH into EC2**: Using `appleboy/ssh-action`
3. **Pre-upgrade DB snapshot**: `pg_dump -Fc` safety net
4. **Pull + rebuild**: `git pull origin production` + `docker compose up -d --build`
5. **Module upgrade**: `-u invoice_agent --stop-after-init`
6. **Health check**: Polls `/web/login` up to 60s for HTTP 200
7. **Rollback on failure**: `git checkout` to previous SHA, rebuild, restart

---

## 9. Deploy Procedure

### 9.1 Normal Deploy (Automated via CI)

1. Open PR → CI runs lint + tests
2. Merge to `production` branch
3. `deploy.yml` triggers automatically
4. Watch GitHub Actions for green checkmark
5. Verify at `https://invoices.<domain>`

### 9.2 Manual Deploy (Emergency)

```bash
# SSH into EC2
ssh -i ~/.ssh/invoice-agent.pem ubuntu@<elastic-ip>

# Navigate to repo
cd /opt/odoo

# Pull latest
git pull origin production

# Build and restart
docker compose up -d --build

# Run module upgrade
docker compose exec -T odoo odoo -u invoice_agent --stop-after-init --log-level=warn

# Restart Odoo
docker compose restart odoo

# Verify health
curl -s -o /dev/null -w "%{http_code}" http://localhost:8069/web/login
# → 200
```

---

## 10. Rollback Procedure

### 10.1 Automatic Rollback (CI-Triggered)

If the health check fails, `deploy.yml` automatically:
1. `git checkout` to the previous SHA (recorded before `git pull`)
2. `docker compose up -d --build`
3. Verifies health again
4. If rollback fails too → manual intervention required

### 10.2 Manual Rollback

```bash
# SSH into EC2
ssh -i ~/.ssh/invoice-agent.pem ubuntu@<elastic-ip>

cd /opt/odoo

# List recent SHAs
git log --oneline -10

# Roll back to specific SHA
git checkout <previous-sha>
docker compose up -d --build
docker compose restart odoo

# Verify
curl -s -o /dev/null -w "%{http_code}" http://localhost:8069/web/login
```

### 10.3 Database Rollback

If a module upgrade corrupted data:

```bash
# List pre-upgrade dumps
docker compose exec db ls -la /tmp/pre_deploy_*.dump

# Restore
docker compose exec -T db pg_restore -U odoo -d odoo \
    --clean --if-exists --no-owner \
    /tmp/pre_deploy_<timestamp>.dump

# Restart Odoo
docker compose restart odoo
```

---

## 11. Disaster Recovery — Full Rebuild from Zero

This procedure proves **nothing critical lives inside a snowflake container**.

### 11.1 Prerequisites

- Latest DB dump on S3 (or local backup)
- Filestore tar on S3 (or local backup)

### 11.2 Recovery Steps

```bash
# 1. Destroy everything
cd /opt/odoo
docker compose down -v    # DESTRUCTIVE — removes all named volumes

# 2. Clone fresh
cd /opt
mv odoo odoo.bak          # Keep old as fallback
git clone <repo-url> odoo
cd odoo

# 3. Recreate .env file
cat > .env << 'EOF'
POSTGRES_DB=odoo
POSTGRES_USER=odoo
POSTGRES_PASSWORD=<your-password>
EOF

# 4. Restore database
aws s3 cp s3://<backup-bucket>/odoo_latest.dump /tmp/
docker compose up -d db
sleep 10  # wait for postgres to be healthy
docker compose exec -T db pg_restore -U odoo -d odoo \
    --clean --if-exists --no-owner \
    < /tmp/odoo_latest.dump

# 5. Restore filestore
aws s3 cp s3://<backup-bucket>/filestore_latest.tar.gz /tmp/
docker compose up -d odoo
docker compose exec -T odoo tar xzf /tmp/filestore_latest.tar.gz \
    -C /var/lib/odoo/filestore/

# 6. Start full stack
docker compose up -d

# 7. Verify
curl -s -o /dev/null -w "%{http_code}" https://invoices.<domain>/web/login
# → 200

# 8. Certbot — reissue certificate (if volume was deleted)
docker compose run --rm certbot certonly --webroot \
    -w /var/www/certbot -d invoices.<domain>
docker compose exec nginx nginx -s reload
```

### 11.3 Measure Recovery Time

```bash
# Time the recovery:
time sh -c '
    docker compose down -v
    docker compose up -d
    # ... restore steps ...
    echo "Recovery complete"
'
```

**Target:** Full recovery in under 30 minutes.

---

## 12. TLS Grading & Security Checks

### 12.1 SSL Labs Grade

1. Visit `https://www.ssllabs.com/ssltest/analyze.html?d=invoices.<domain>`
2. Wait for the scan to complete
3. **Target grade: A or A+**
   - A+ requires HSTS with `max-age >= 31536000`

### 12.2 Manual Header Checks

```bash
# TLS version and cipher
curl -v --tlsv1.2 https://invoices.<domain>/ 2>&1 | grep "SSL connection"

# HSTS header
curl -sI https://invoices.<domain> | grep -i strict-transport

# No mixed content
curl -s https://invoices.<domain>/web/login | grep -oP 'src="[^"]*' | grep '^http:' | head -5
# Should return nothing

# Certificate info
echo | openssl s_client -connect invoices.<domain>:443 2>/dev/null | \
    openssl x509 -noout -subject -issuer -dates
```

### 12.3 OWASP Recommendations Met

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| TLS 1.2+ only | ✅ | `ssl_protocols TLSv1.2 TLSv1.3;` |
| Strong ciphers | ✅ | Modern cipher suite, no RC4/DES/3DES |
| HSTS | ✅ | `max-age=31536000; includeSubDomains` |
| HTTP → HTTPS redirect | ✅ | `return 301` in port 80 server block |
| No mixed content | ✅ | All assets served over HTTPS via proxy |
| Secure cookies (Odoo) | ✅ | Handled by `proxy_mode = True` + `secure` flag |
| OCSP Stapling | 🔲 Optional | Add `ssl_stapling on;` if needed |
| CSP Headers | 🔲 Optional | Add via additional addons if needed |

---

## 13. Monitoring & Health Checks

### 13.1 Certbot Renewal Test

```bash
# Monthly scheduled check (cron/systemd timer)
0 0 1 * * /usr/bin/docker compose -f /opt/odoo/docker-compose.yml \
    run --rm certbot renew --dry-run >> /var/log/certbot-renew.log 2>&1
```

### 13.2 Docker Health

```bash
# Container status
docker compose ps

# Each container should show "Up" status
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
```

### 13.3 Odoo Health Endpoint

```bash
# Basic connectivity test
curl -s -o /dev/null -w "%{http_code}" https://invoices.<domain>/web/login

# More thorough: confirm the page has expected content
curl -s https://invoices.<domain>/web/login | grep -q 'Odoo'
echo $?  # → 0 if Odoo is responding
```

### 13.4 Log Management

```bash
# Tail all logs
docker compose logs -f --tail=100

# Filter by service
docker compose logs -f nginx
docker compose logs -f odoo
docker compose logs -f db

# Search for errors
docker compose logs odoo | grep -i "ERROR\|CRITICAL\|TRACEBACK"
```

---

## 14. Troubleshooting

### 14.1 Certificate Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Certificate expired | Auto-renewal failed | Run `docker compose run --rm certbot renew` manually |
| "Cannot find domain" | DNS not propagated | Verify `dig +short invoices.<domain>` returns correct IP |
| ACME challenge fails | Port 80 not open | Check security group allows `0.0.0.0/0:80` |
| ACME challenge fails (2) | `.well-known` location wrong | Verify `location /.well-known/acme-challenge/` in nginx config |

### 14.2 Nginx Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 502 Bad Gateway | Odoo not running | `docker compose ps odoo` → should show "Up" |
| 502 on `/websocket` | Wrong upstream port | Ensure `/websocket` → `odoo:8072`, not `odoo:8069` |
| 413 Request Entity Too Large | Upload exceeds `client_max_body_size` | Increase in nginx config |
| 504 Gateway Timeout | Odoo request too slow | Increase `proxy_read_timeout` |
| Mixed content warnings | `X-Forwarded-Proto` not set | Verify `proxy_set_header X-Forwarded-Proto $scheme;` |

### 14.3 Odoo Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| All clients appear as 172.x.x.x (Docker IP) | `proxy_mode` not enabled | Set `PROXY_MODE: "True"` in docker-compose.yml |
| Redirect loop (http→https→http) | `X-Forwarded-Proto` not trusted | Same as above — proxy_mode controls this |
| Odoo generates `http://` URLs | Proxy mode off or wrong header | Verify nginx sends `X-Forwarded-Proto: https` |
| Websocket fails to connect | Missing `Upgrade`/`Connection` headers | Check nginx `/websocket` location block |

### 14.4 Quick Diagnostic Commands

```bash
# Full stack status
docker compose ps

# Odoo logs — last 50 lines
docker compose logs --tail=50 odoo

# Nginx access log
docker compose exec nginx cat /var/log/nginx/access.log | tail -20

# Nginx error log
docker compose exec nginx cat /var/log/nginx/error.log | tail -20

# Check if proxy headers are being set (from inside nginx)
docker compose exec nginx sh -c "apk add curl && curl -v http://odoo:8069/web/login 2>&1 | grep -i 'x-forwarded'"

# Test Odoo directly (bypass nginx)
docker compose exec odoo curl -s -o /dev/null -w "%{http_code}" http://localhost:8069/web/login

# DNS resolution
dig +short invoices.<domain>

# Certificate expiry
echo | openssl s_client -connect invoices.<domain>:443 2>/dev/null | \
    openssl x509 -noout -enddate
```

---

## Appendix A: Quick Reference Commands

```bash
# ──────── Certificate ────────
docker compose run --rm certbot certonly --webroot -w /var/www/certbot -d invoices.<domain>
docker compose run --rm certbot renew --dry-run
docker compose exec nginx nginx -s reload

# ──────── Docker ────────
docker compose up -d --build
docker compose down -v
docker compose logs -f nginx
docker compose exec odoo odoo -u invoice_agent --stop-after-init

# ──────── Verify ────────
curl -sI https://invoices.<domain>
dig +short invoices.<domain>
nc -vz invoices.<domain> 443

# ──────── Backup ────────
docker compose exec -T db pg_dump -U odoo -Fc --no-owner -f /tmp/backup.dump odoo
```

## Appendix B: File Layout on EC2

```
/opt/odoo/
├── docker-compose.yml          # Main compose file with all 4 services
├── Dockerfile                  # Odoo image build
├── .env                        # Secrets (NOT in git)
├── nginx/
│   └── conf.d/
│       └── odoo.conf           # Nginx reverse proxy config
├── custom_addons/
│   └── invoice_agent/          # Active development addon
├── .github/workflows/
│   ├── ci.yml                  # Lint + test on PR
│   └── deploy.yml              # Auto-deploy on push to production
└── docs/
    └── deployment.md           # This document
