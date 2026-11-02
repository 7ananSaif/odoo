#!/usr/bin/env bash
# smoke-test-eks.sh — post-deploy smoke test for the EKS Odoo stack.
#
# WHY THIS EXISTS
# --------------
# deploy.yml used to call scripts/smoke-test.sh, which is written for the local
# docker-compose topology: it probes invoice-ai (localhost:8100), RabbitMQ
# (15672), Prometheus (9090) and Grafana (3000) on localhost.
#
# Neither half of that assumption holds for the EKS deployment:
#   * full-infra/helm/odoo-stack deploys Odoo + filestore PVC only (Postgres is RDS,
#     see values.production.yaml), so those services are not in the cluster;
#   * on a GitHub runner, localhost exposes none of them either.
# The test therefore failed on every run, which - with the automatic rollback -
# meant no deploy could ever stay up.
#
# This script validates the surface that is actually deployed and that a real
# user depends on: the public HTTPS Odoo endpoint.
#
# Usage:
#   ./scripts/smoke-test-eks.sh <domain> [login-path]
#   ./scripts/smoke-test-eks.sh example.com
#   ./scripts/smoke-test-eks.sh example.com /web/login
#
# Exit code 0 = pass, 1 = failure (this triggers the rollback in deploy.yml).

set -euo pipefail

DOMAIN="${1:-}"
LOGIN_PATH="${2:-/web/login}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo -e "${GREEN}PASS${NC}: $*"; }
fail() { FAIL=$((FAIL + 1)); echo -e "${RED}FAIL${NC}: $*"; }
warn() { echo -e "${YELLOW}WARN${NC}: $*"; }

if [ "$DOMAIN" = "--help" ] || [ "$DOMAIN" = "-h" ]; then
    sed -n '2,30p' "$0"
    exit 0
fi

echo ""
echo "============================================"
echo "EKS smoke test — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Target: https://${DOMAIN}${LOGIN_PATH}"
echo "============================================"
echo ""

if [ -z "$DOMAIN" ]; then
    fail "no domain supplied — pass one as the first argument (deploy.yml uses secrets.DOMAIN)"
    echo ""
    echo -e "${RED}SMOKE TEST FAILED${NC}"
    exit 1
fi

BASE_URL="https://${DOMAIN}"

# ---------------------------------------------------------------------------
# 1. TLS handshake — a certificate problem must fail the deploy.
# ---------------------------------------------------------------------------
echo "--- TLS ---"
if echo | openssl s_client -connect "${DOMAIN}:443" -servername "${DOMAIN}" >/dev/null 2>&1; then
    pass "TLS handshake with ${DOMAIN}:443 succeeded"
else
    fail "TLS handshake with ${DOMAIN}:443 failed (no certificate or port 443 unreachable)"
fi

cert_dates=$(echo | openssl s_client -connect "${DOMAIN}:443" -servername "${DOMAIN}" 2>/dev/null \
    | openssl x509 -noout -enddate 2>/dev/null || echo "")
if [ -n "$cert_dates" ]; then
    expiry="${cert_dates#notAfter=}"
    pass "TLS certificate retrieved"
    echo "  Expires: ${expiry}"
    if expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null); then
        now_epoch=$(date +%s)
        days_left=$(( (expiry_epoch - now_epoch) / 86400 ))
        if [ "$days_left" -lt 0 ]; then
            fail "TLS certificate expired ${days_left#-} day(s) ago"
        elif [ "$days_left" -lt 14 ]; then
            warn "TLS certificate expires in ${days_left} day(s)"
        else
            pass "TLS certificate valid for ${days_left} day(s)"
        fi
    fi
else
    warn "Could not read the certificate expiry date"
fi

# ---------------------------------------------------------------------------
# 2. The login page — the real user entry point, and proof Odoo can reach RDS.
#    Odoo cannot render this page at all if its database is unreachable.
# ---------------------------------------------------------------------------
echo ""
echo "--- Odoo login page ---"
body_file=$(mktemp)
trap 'rm -f "$body_file"' EXIT

login_code=$(curl -sS -o "$body_file" -w '%{http_code}' -L --max-time 30 \
    "${BASE_URL}${LOGIN_PATH}" 2>/dev/null || echo "000")

case "$login_code" in
    200|302|303)
        pass "${LOGIN_PATH} responded (HTTP ${login_code})"
        ;;
    *)
        fail "${LOGIN_PATH} not responding (HTTP ${login_code}, expected 200/302/303)"
        ;;
esac

if [ -s "$body_file" ]; then
    body_bytes=$(wc -c < "$body_file" | tr -d ' ')
    if grep -qiE '<form|oe_login' "$body_file"; then
        pass "login page looks like an Odoo page (${body_bytes} bytes, login form present)"
    else
        fail "login page did not contain an Odoo login form (${body_bytes} bytes) — check the ALB target group"
    fi
else
    fail "login page returned an empty body"
fi

# ---------------------------------------------------------------------------
# 3. Informational checks — reported, never fatal, so a healthy deploy cannot
#    be rolled back for a cosmetic reason.
# ---------------------------------------------------------------------------
echo ""
echo "--- Informational ---"

health_code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
    "${BASE_URL}/web/health" 2>/dev/null || echo "000")
if [ "$health_code" = "200" ]; then
    pass "/web/health responded (HTTP 200)"
else
    warn "/web/health responded HTTP ${health_code} (the chart's readiness probe uses this path; it may simply not be routed through the ALB)"
fi

redirect_code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
    "http://${DOMAIN}${LOGIN_PATH}" 2>/dev/null || echo "000")
case "$redirect_code" in
    301|302|307|308)
        pass "plain HTTP redirects to HTTPS (HTTP ${redirect_code})"
        ;;
    *)
        warn "plain HTTP returned HTTP ${redirect_code} rather than a redirect to HTTPS"
        ;;
esac

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================"
echo "Smoke test summary"
echo "============================================"
echo -e "Passed: ${GREEN}${PASS}${NC}"
echo -e "Failed: ${RED}${FAIL}${NC}"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}ALL TESTS PASSED${NC}"
    exit 0
fi

echo -e "${RED}${FAIL} TEST(S) FAILED${NC}"
exit 1
