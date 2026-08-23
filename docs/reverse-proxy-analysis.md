# Reverse Proxy Semantics for Odoo and WebSockets

> **Deep technical reference** covering `proxy_mode = True`, trusted header forwarding, WebSocket upgrade handshake, and ACME HTTP-01 challenge mechanics.

---

## Table of Contents

1. [`proxy_mode = True` Semantics](#1-proxy_mode--true-semantics)
2. [Trusted Headers: `X-Forwarded-For` and `X-Forwarded-Proto`](#2-trusted-headers-x-forwarded-for-and-x-forwarded-proto)
3. [WebSocket Upgrade Handshake](#3-websocket-upgrade-handshake)
4. [ACME HTTP-01 Challenge](#4-acme-http-01-challenge)
5. [Integration: How It All Fits Together](#5-integration-how-it-all-fits-together)
6. [Failure Scenarios & Diagnostics](#6-failure-scenarios--diagnostics)

---

## 1. `proxy_mode = True` Semantics

### 1.1 Where It's Set

```ini
# odoo.conf (legacy)
[options]
proxy_mode = True

# docker-compose.yml (modern — our approach)
environment:
  PROXY_MODE: "True"
```

The official `odoo:19` entrypoint (`/entrypoint.sh`) reads the `PROXY_MODE` environment variable and writes it into `odoo.conf` before starting the Odoo process.

### 1.2 What It Controls in `odoo/http.py`

When `proxy_mode = True`, Odoo's HTTP layer (`odoo/http.py`) modifies the **werkzeug request wrapper** to trust proxy headers.

**Without `proxy_mode`:**

```python
# odoo/http.py — simplified normal flow
class Root:
    def get_request(self, httprequest):
        remote_addr = httprequest.remote_addr  # ← Docker network IP: 172.17.0.x
        scheme = httprequest.scheme             # ← 'http' (always, since traffic comes from nginx over plain HTTP)
```

Every client appears to come from the **nginx container IP** (e.g., `172.17.0.3`). Odoo always thinks the scheme is `http`, even when the original request was HTTPS.

**With `proxy_mode`:**

```python
# odoo/http.py — simplified with proxy_mode
class Root:
    def get_request(self, httprequest):
        if odoo.tools.config['proxy_mode']:
            # Trust X-Forwarded-For for the real client IP
            xff = httprequest.headers.get('X-Forwarded-For', '')
            remote_addr = xff.split(',')[0].strip() if xff else httprequest.remote_addr
            
            # Trust X-Forwarded-Proto for the scheme
            scheme = httprequest.headers.get('X-Forwarded-Proto', 'http')
            
            # Mark as not running through werkzeug's serving infrastructure
            # (this prevents werkzeug from applying its own proxy logic)
            httprequest.environ['werkzeug.serving'] = False
        else:
            remote_addr = httprequest.remote_addr
            scheme = httprequest.scheme
```

**The actual code path** in Odoo 19.0 (`odoo/http.py`, `Root._get_request()`):

```python
# Near line 2000+ in odoo/http.py
request = werkzeug.wrappers.Request(httprequest.environ)
if config['proxy_mode']:
    request.remote_addr = httprequest.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    request.httprequest.remote_addr = request.remote_addr
    # scheme detection
    if httprequest.headers.get('X-Forwarded-Proto'):
        request.httprequest.environ['wsgi.url_scheme'] = httprequest.headers['X-Forwarded-Proto']
```

### 1.3 What Breaks Without It

| Component | Without `proxy_mode` | With `proxy_mode` |
|-----------|---------------------|-------------------|
| Client IP in logs | `172.17.0.3` (nginx) | `203.0.113.42` (real client) |
| GeoIP/geolocation | Always shows AWS zone | Shows real client location |
| IP-based access control | Doesn't match user IPs | Correctly matches |
| Redirect URLs | `http://invoices.domain.com/...` | `https://invoices.domain.com/...` |
| OAuth/SSO redirects | Mismatched scheme → errors | Correct scheme → works |
| Security audit | All traffic from one IP | Proper audit trail |
| Rate limiting | Rate-limits all users as one | Per-client rate limiting |

### 1.4 The Nginx-Odoo Header Chain

```
Browser                              Nginx                              Odoo
  │                                    │                                  │
  │── GET /web/login ──────────────────│                                  │
  │   Host: invoices.domain.com        │                                  │
  │   (no proxy headers)               │                                  │
  │                                    │── GET /web/login ───────────────│
  │                                    │   Host: invoices.domain.com      │
  │                                    │   X-Forwarded-For: 203.0.113.42 │
  │                                    │   X-Forwarded-Proto: https      │
  │                                    │   X-Real-IP: 203.0.113.42       │
  │                                    │                                  │
  │                                    │  ┌── proxy_mode reads ──────┐   │
  │                                    │  │ remote_addr = 203.0.113.42│   │
  │                                    │  │ scheme = "https"          │   │
  │                                    │  └──────────────────────────┘   │
```

---

## 2. Trusted Headers: `X-Forwarded-For` and `X-Forwarded-Proto`

### 2.1 Header Format

**`X-Forwarded-For`** (RFC 7239 superseded this with `Forwarded`, but Odoo uses the old header):
```
X-Forwarded-For: <client>, <proxy1>, <proxy2>
```

Nginx sets this with `$proxy_add_x_forwarded_for`, which **appends** to any existing value. If there's a chain of reverse proxies, each one adds to the list.

**`X-Forwarded-Proto`**:
```
X-Forwarded-Proto: https
```

Tells the backend what protocol the original client used. If absent, Odoo defaults to `http`.

### 2.2 What Nginx Sends

From our config:

```nginx
proxy_set_header Host              $host;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Real-IP         $remote_addr;
proxy_redirect off;
```

| Variable | Nginx Expands To | Example |
|----------|-----------------|---------|
| `$host` | The `Host` header from the original request | `invoices.domain.com` |
| `$proxy_add_x_forwarded_for` | `$remote_addr` if no XFF exists, or `$http_x_forwarded_for, $remote_addr` | `203.0.113.42` or `10.0.0.1, 203.0.113.42` |
| `$scheme` | `http` or `https` depending on the listening server block | `https` (if on port 443) |
| `$remote_addr` | The IP of the immediate client | `203.0.113.42` (or `10.x.x.x` if behind ELB) |

### 2.3 Multi-Proxy Chain

If the EC2 is behind an AWS ALB and then nginx:

```
Client → AWS ALB → Nginx → Odoo

X-Forwarded-For: 203.0.113.42, 10.0.1.5
                 ^client          ^ALB private IP

Nginx adds: $proxy_add_x_forwarded_for
→ X-Forwarded-For: 203.0.113.42, 10.0.1.5, nginx-private-ip
```

Odoo with `proxy_mode` takes the **first** IP: `203.0.113.42` — the real client.

### 2.4 Security Consideration: Spoofing

If the public internet can reach Odoo directly (port 8069 open), anyone can forge headers:

```bash
curl -H "X-Forwarded-For: 127.0.0.1" http://<ec2>:8069/web/login
# Odoo would think the request came from localhost!
```

**Mitigation:** Port 8069 is bound to `127.0.0.1` on the host, AND the security group blocks it. Only nginx (which always sets these headers correctly) can reach Odoo. Never expose Odoo directly to the internet with `proxy_mode = True`.

---

## 3. WebSocket Upgrade Handshake

### 3.1 The HTTP→WebSocket Upgrade Handshake

WebSocket connections start as standard HTTP requests and then **upgrade** the protocol:

**Step 1 — Client sends upgrade request:**

```
GET /websocket HTTP/1.1
Host: invoices.domain.com
Upgrade: websocket                             # ← tells server to switch protocols
Connection: Upgrade                            # ← required with Upgrade header
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==   # ← base64-encoded 16-byte random key
Sec-WebSocket-Version: 13                      # ← WebSocket protocol version
Origin: https://invoices.domain.com            # ← CORS-like origin check
```

**Step 2 — Server responds with 101 Switching Protocols:**

```
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=   # ← SHA-1 hash of key + magic GUID
```

**Step 3 — Bidirectional WebSocket frames begin:**

After the handshake, the connection upgrades from HTTP to the WebSocket protocol. Both sides can now send and receive frames at any time.

### 3.2 Why `/websocket` Needs Special Headers in Nginx

Without explicit `Upgrade` and `Connection` headers, nginx will treat the request as a **normal HTTP request**:

```nginx
# WRONG — Odoo never sees the Upgrade request
location /websocket {
    proxy_pass http://odoo:8069;
    # Missing: proxy_set_header Upgrade $http_upgrade;
    # Missing: proxy_set_header Connection "upgrade";
}
```

Result: The browser's WebSocket connection **hangs** or gets **400 Bad Request** because:

1. Nginx forwards `GET /websocket` to Odoo on port 8069 (HTTP worker)
2. Odoo's HTTP worker doesn't know about the upgrade request
3. The browser waits for a `101 Switching Protocols` that never comes
4. After the timeout, `WebSocket.onerror` fires with no clear error message

**Correct configuration:**

```nginx
location /websocket {
    proxy_pass http://odoo:8072;                    # ← gevent longpoll worker
    proxy_set_header Upgrade    $http_upgrade;       # ← passes client's Upgrade header
    proxy_set_header Connection "upgrade";           # ← forces Connection: upgrade
    proxy_read_timeout 86400s;                       # ← don't timeout idle WebSockets
    proxy_buffering off;                             # ← must stream, not buffer
    proxy_request_buffering off;
}
```

### 3.3 The `$http_upgrade` Variable

Nginx's `$http_upgrade` comes from `$http_<header_name>` — it captures the value of the `Upgrade` header from the original request. For WebSocket connections, this is `websocket`. For other upgrade protocols (HTTP/2, h2c), it could be different values.

By using `proxy_set_header Upgrade $http_upgrade`, we pass through whatever upgrade protocol the client requested.

### 3.4 Why Port 8072 (Longpoll Worker)

Odoo has two types of workers:

| Port | Worker Type | Protocol | Purpose |
|------|-------------|----------|---------|
| 8069 | Regular HTTP | HTTP/1.1 | Normal web requests, JSON-RPC, web controllers |
| 8072 | Longpoll / Gevent | HTTP + WebSocket | Bus connections, real-time notifications, live chat, kanban updates |

The longpoll worker on 8072 is **gevent-based** and designed for:
- Many simultaneous open connections (thousands)
- Long-lived connections that may idle for hours
- WebSocket protocol handling
- Pushing events to connected clients

If you proxy `/websocket` to port 8069 instead of 8072, the regular HTTP worker will:
1. Try to process it as a normal HTTP request
2. Not handle the upgrade properly
3. Return `200 OK` instead of `101 Switching Protocols`
4. The browser's WebSocket will silently fail

### 3.5 Verifying the WebSocket Connection

**From a browser:**

```javascript
const ws = new WebSocket('wss://invoices.domain.com/websocket');
ws.onopen = () => console.log('✅ WebSocket connected');
ws.onclose = (e) => console.log('❌ WebSocket closed:', e.code, e.reason);
ws.onerror = (e) => console.error('❌ WebSocket error:', e);
ws.onmessage = (msg) => console.log('📨 Received:', msg.data);
```

**From the Network tab in Chrome DevTools:**

1. Open DevTools → Network tab
2. Filter by "WS" (WebSocket)
3. Click the WebSocket connection
4. Look at **Headers** tab → verify `101 Switching Protocols`
5. Look at **Messages** tab → verify frames are being exchanged

**From curl (limited test — doesn't complete the handshake):**

```bash
curl -v \
    -H "Connection: Upgrade" \
    -H "Upgrade: websocket" \
    -H "Sec-WebSocket-Version: 13" \
    -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
    https://invoices.domain.com/websocket \
    2>&1 | grep -E "HTTP/|Switching"
# Expected: HTTP/1.1 101 Switching Protocols
```

### 3.6 Websocket Timeout Considerations

| Scenario | Recommended `proxy_read_timeout` | Rationale |
|----------|-------------------------------|-----------|
| Normal Odoo without long polling | `720s` (12 min) | Standard requests complete quickly |
| Odoo with bus/livechat/kanban | `86400s` (24h) | Idle WebSockets shouldn't be terminated |
| Invoice scanning queue | `86400s` (24h) | Users may keep queue kanban open all day |

---

## 4. ACME HTTP-01 Challenge

### 4.1 What the ACME HTTP-01 Challenge Proves

The HTTP-01 challenge proves **domain control** — that the person requesting the certificate actually controls the domain.

**The challenge flow:**

```
Let's Encrypt                          Nginx (invoices.domain.com:80)
    │                                          │
    │ 1. Generate token: "abc123_def456"       │
    │                                          │
    │ 2. Send challenge request:               │
    │    GET http://invoices.domain.com/        │
    │    .well-known/acme-challenge/abc123_def456│
    │                                          │
    │    ← HTTP 200 + token.thumbprint          │
    │                                          │
    │ 3. Verify: token + thumbprint match?      │
    │                                          │
    │ 4. Issue certificate if valid ───────────│
```

### 4.2 Why the Challenge Goes Through Port 80 (Not 443)

The HTTP-01 challenge uses **port 80** for a deliberate reason:

1. **Bootstrap problem**: You need a certificate for HTTPS, but you can't prove domain control over HTTPS without a certificate. Port 80 (HTTP) is bootstrap-able because it doesn't require TLS.

2. **Simplicity**: HTTP is simpler than HTTPS for this purpose — no TLS handshake, no certificate chain verification.

3. **Widely accessible**: Port 80 is almost never firewalled (due to its essential nature), while port 443 could be blocked or filtered.

4. **Alternative** — TLS-ALPN-01 (port 443): Let's Encrypt also supports the TLS-ALPN-01 challenge that works over port 443 using TLS handshake information, but it requires the webserver to be configured with the `acme-tls/1` ALPN protocol. The HTTP-01 challenge is simpler and more widely supported.

### 4.3 Our Implementation

The nginx config has a special block **before** the HTTP→HTTPS redirect:

```nginx
server {
    listen 80;
    server_name invoices.domain.com;

    # ACME HTTP-01 challenge — served BEFORE the redirect
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
        try_files $uri =404;
    }

    # Everything else → HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}
```

**Why it works:** Nginx matches `location /.well-known/acme-challenge/` before the `/` catch-all. Requests to `http://invoices.domain.com/.well-known/acme-challenge/<token>` are served from `/var/www/certbot/.well-known/acme-challenge/<token>`, which the certbot container writes to.

### 4.4 What Happens Without the ACME Location

If the challenge location is missing:

1. Certbot tries to write the challenge file → writes to `/var/www/certbot/.well-known/acme-challenge/<token>`
2. Let's Encrypt tries to fetch `http://invoices.domain.com/.well-known/acme-challenge/<token>`
3. Nginx's `/` catch-all sends a `301 Moved Permanently` → `https://...`
4. Let's Encrypt follows the redirect to HTTPS → but there's no certificate yet on HTTPS → TLS handshake fails
5. Challenge fails with `Connection refused` or `certificate error`

**The error message from certbot:**
```
Failed to connect to invoices.domain.com for HTTP-01 challenge.
The domain does not resolve to this server or port 80 is not reachable.
```

### 4.5 Webroot vs. Nginx Plugin vs. Standalone

| Method | How It Works | Our Choice |
|--------|-------------|------------|
| **Webroot** | Writes challenge files to a directory served by the web server | ✅ (`-w /var/www/certbot`) |
| **Nginx plugin** | Certbot modifies nginx config to serve the challenge | ❌ (requires plugin to be installed) |
| **Standalone** | Certbot runs its own temporary HTTP server on port 80 | ❌ (conflicts with running nginx) |

We use **webroot** because it doesn't require stopping nginx, installing plugins, or modifying configs at runtime.

---

## 5. Integration: How It All Fits Together

### 5.1 Full Request Flow

```
                                  ┌─────────────────────────┐
                                  │  Let's Encrypt (ACME)    │
                                  │  certbot certonly        │
                                  └────────────┬────────────┘
                                               │
                                               │ HTTP-01: GET /.well-known/acme-challenge/<token>
                                               ▼
┌──────────┐     ┌──────────┐     ┌───────────────────────┐
│ Browser  │────►│ Route 53 │────►│  EC2 Security Group   │
│ (User)   │     │ A record │     │  80: open ✓           │
└──────────┘     └──────────┘     │  443: open ✓          │
                                  │  8069: CLOSED ✗       │
                                  └──────────┬────────────┘
                                             │
                                    ┌────────┴────────┐
                                    │  docker host     │
                                    │  (EC2 instance)  │
                                    └────────┬────────┘
                                             │
                    ┌────────────────────────┼────────────────────┐
                    │                        │                     │
              ┌─────┴─────┐          ┌───────┴────────┐           │
              │  Nginx    │          │   Nginx        │           │
              │  port 80  │          │   port 443     │           │
              │           │          │   HTTPS + HSTS │           │
              │ /.well-   │          │   ssl_cert     │           │
              │ known/    │          └───────┬────────┘           │
              │ ⤶ serve   │                  │                    │
              │ static    │           ┌──────┴──────┐             │
              └───────────┘           │  location /  │  location /websocket
                                      │  proxy_pass  │  proxy_pass
                                      │  odoo:8069   │  odoo:8072
                                      │  +headers    │  +Upgrade+Connection
                                      └──────┬───────┘  └─────────┬─────────┘
                                             │                    │
                                      ┌──────┴──────┐    ┌────────┴────────┐
                                      │  Odoo HTTP  │    │  Odoo Longpoll │
                                      │  port 8069  │    │  port 8072     │
                                      │  proxy_mode │    │  (gevent)      │
                                      └─────────────┘    └─────────────────┘
```

### 5.2 Certificate Lifecycle

```
Issue (day 0):   certonly --webroot   ──► /etc/letsencrypt/live/invoices.domain.com/
                                              ├── fullchain.pem
                                              ├── privkey.pem
                                              └── cert.pem

Auto-renewal:    certbot renew --webroot
                 (every 12h; renews if <30d until expiry)
                                              │
                                              ▼
                 nginx -s reload   ──► nginx picks up new certs (zero-downtime)

Dry-run test:    certbot renew --dry-run
                 (monthly cron; verifies everything works without renewing)
```

---

## 6. Failure Scenarios & Diagnostics

### 6.1 Proxy Mode Not Enabled

**Symptom:** All client IPs in Odoo logs show `172.17.0.x` (Docker network IP). Redirect URLs show `http://` even for HTTPS requests.

**Logs to check:**
```bash
docker compose logs odoo | grep -i "remote addr"
# Shows: remote_addr=172.17.0.3 (nginx) instead of real client IP
```

**Root cause:** `proxy_mode` is not set in odoo.conf or PROXY_MODE env var is missing.

**Fix:**
```bash
# Add to docker-compose.yml under odoo.environment:
#   PROXY_MODE: "True"
# Then:
docker compose up -d odoo
docker compose restart odoo
```

### 6.2 All HTTPS Redirects Become HTTP://

**Symptom:** Clicking "Sign in" or any link redirects to `http://invoices.domain.com/web/login` instead of `https://...`

**Logs to check:**
```bash
# Check what scheme Odoo thinks it's running under
docker compose logs odoo | grep -i "scheme\|url_scheme"
```

**Root cause:** `proxy_mode` not set, OR `X-Forwarded-Proto` not being sent by nginx.

**Fix:** Verify both:
1. `PROXY_MODE: "True"` is set
2. `proxy_set_header X-Forwarded-Proto $scheme;` is in the nginx location block

### 6.3 WebSocket Connection Hangs

**Symptom:** Odoo loads but live chat, bus notifications, kanban queue updates don't work. Browser DevTools shows WebSocket connection pending then closed.

**Logs to check:**
```bash
# Check if the WebSocket request reaches Odoo
docker compose logs nginx | grep "/websocket"
# Should show: "101" in the status column

# Check Odoo longpoll logs
docker compose logs odoo | grep -i "websocket\|bus\|gevent"
```

**Root cause:** Missing `Upgrade`/`Connection` headers in nginx `/websocket` block.

**Fix:**
```nginx
location /websocket {
    proxy_pass http://odoo_ws_upstream;
    proxy_set_header Upgrade    $http_upgrade;       # ← MUST have
    proxy_set_header Connection "upgrade";            # ← MUST have
    proxy_read_timeout 86400s;
    proxy_buffering off;
}
```

### 6.4 ACME Challenge Fails with 301

**Symptom:** `certbot certonly` fails with `The server experienced a TLS error during the HTTP-01 challenge`.

**Logs to check:**
```bash
# Check nginx access log for the challenge request
docker compose exec nginx cat /var/log/nginx/access.log | grep "acme-challenge"
# If you see "301" instead of "200", the challenge is being redirected
```

**Root cause:** The `return 301` in the port 80 server block fires before the `location /.well-known/acme-challenge/` is matched — but this should NOT happen if the config is correct (location blocks have higher priority than the `=` / `location` prefix).

**Fix:** Ensure the ACME location block is placed **before** the catch-all in the port 80 server block:

```nginx
server {
    listen 80;
    location /.well-known/acme-challenge/ {  # ← FIRST
        root /var/www/certbot;
        try_files $uri =404;
    }
    location / {  # ← SECOND (catch-all)
        return 301 https://$host$request_uri;
    }
}
```

**Verify:**
```bash
curl -I http://invoices.domain.com/.well-known/acme-challenge/test
# Expected: HTTP/1.1 404 NOT FOUND (file doesn't exist yet, but location matches)
# NOT: HTTP/1.1 301 MOVED PERMANENTLY
```

### 6.5 Certificate Expired

**Symptom:** Browser shows "Your connection is not private" or "NET::ERR_CERT_DATE_INVALID".

**Logs to check:**
```bash
# Check certbot logs
docker compose logs certbot --tail=50

# Check certificate expiry
echo | openssl s_client -connect invoices.domain.com:443 2>/dev/null | \
    openssl x509 -noout -enddate
# Shows: notAfter=Aug 30 12:00:00 2026 GMT
```

**Root cause:** Certbot auto-renewal failed (e.g., certbot container was down, port 80 was blocked, DNS changed).

**Fix:**
```bash
# Manually renew
docker compose run --rm certbot renew
docker compose exec nginx nginx -s reload
```

### 6.6 HSTS Prevents HTTP Access During Debugging

**Symptom:** After enabling HSTS, accessing `http://invoices.domain.com` in a browser that has previously visited the site always redirects to HTTPS, even if nginx is temporarily serving HTTP only.

**Why:** Once a browser receives HSTS headers, it will refuse to connect over HTTP for the entire `max-age` period (1 year in our config).

**Workaround:**
1. Use `curl` instead of a browser for debugging: `curl -k http://localhost:8069/web/login`
2. Clear the browser's HSTS cache: `chrome://net-internals/#hsts` → Delete domain
3. Or use an incognito/private window (no stored HSTS)

**Test before enforcing with long max-age:**
```nginx
# Test with short duration first:
add_header Strict-Transport-Security "max-age=300; includeSubDomains" always;
# After testing, increase to 1 year:
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

### 6.7 Quick Diagnostic Matrix

| Symptom | First Check | Second Check | Third Check |
|---------|-------------|--------------|-------------|
| All IPs are 172.x.x.x | `docker compose exec odoo env \| grep PROXY_MODE` | `docker compose exec odoo cat /opt/odoo/etc/odoo.conf \| grep proxy_mode` | Check nginx sends X-Forwarded-For |
| Redirect loop (http→https→http) | `curl -I http://...` → check for 301 | `curl -I https://...` → check for redirect to http | Verify proxy_mode reads X-Forwarded-Proto |
| WebSocket fails to connect | Browser DevTools → Network → WS → see status | `curl -v -H "Upgrade: websocket" ...` → check for 101 | nginx `/websocket` location block |
| Certificate error | `openssl s_client -connect ...:443` → check dates | `docker compose logs certbot \| tail` | DNS resolves to correct IP |
| 502 Bad Gateway | `docker compose ps` → check odoo status | `docker compose logs odoo \| tail` | nginx upstream `odoo:8069` resolves correctly |
| 413 Request Too Large | Check nginx error log | `client_max_body_size` in config | File size < 100 MB |
| Mixed content warnings | `curl -s https://... | grep 'http://'` | X-Forwarded-Proto header | All assets over HTTPS |
