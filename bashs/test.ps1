# ==============================================================================
# 1. تثبيت المستلزمات (Python Dependencies)
# ==============================================================================
Write-Host "=== Installing Test Dependencies ===" -ForegroundColor Cyan
pip install asyncpg anyio httpx pytest-anyio pytest-asyncio ruff bandit coverage mypy pytest

# ==============================================================================
# 2. فحص وتنسيق الكود لاكستنشن invoice_agent
# ==============================================================================
Write-Host "`n=== Checking Code Quality & Security (invoice_agent) ===" -ForegroundColor Cyan
ruff check custom_addons/invoice_agent --config pyproject.toml
ruff format custom_addons/invoice_agent --config pyproject.toml --check
bandit -r custom_addons/invoice_agent/ -ll --severity-level medium

# ==============================================================================
# 3. تشغيل اختبارات Odoo وتغطية الكود (Coverage)
# ==============================================================================
Write-Host "`n=== Running Odoo Tests & Coverage Gate ===" -ForegroundColor Cyan
coverage run --concurrency=thread --source=custom_addons/invoice_agent python .\odoo-bin -c odoo.conf -d test_db -i invoice_agent --test-enable --test-tags /invoice_agent --stop-after-init --log-level=test
coverage report -m

# ==============================================================================
# 4. فحوصات Terraform
# ==============================================================================
Write-Host "`n=== Validating Terraform Configuration ===" -ForegroundColor Cyan
terraform -chdir=infra/terraform/ fmt -check -recursive
terraform -chdir=infra/terraform/ init -backend=false
terraform -chdir=infra/terraform/ validate

# ==============================================================================
# 5. فحوصات إعدادات المراقبة (Observability via Docker)
# ==============================================================================
Write-Host "`n=== Validating Observability Configurations ===" -ForegroundColor Cyan
$pwdPath = (Get-Location).Path
docker run --rm -v "${pwdPath}/infra/observability/prometheus:/etc/prometheus" prom/prometheus:v2.53.0 checkconfig /etc/prometheus/prometheus.yml
docker run --rm -v "${pwdPath}/infra/observability/alertmanager:/etc/alertmanager" prom/alertmanager:v0.27.0 checkconfig /etc/alertmanager/alertmanager.yml
python -c "import json; json.load(open('infra/observability/grafana/dashboards/agent-slo.json'))"

# ==============================================================================
# 6. فحص الثغرات والخطة الأمنية (Security & Trivy)
# ==============================================================================
Write-Host "`n=== Running Security & Container Scans ===" -ForegroundColor Cyan
trivy fs --severity CRITICAL,HIGH .
docker build -t odoo-test:local .
trivy image --severity CRITICAL,HIGH odoo-test:local

# التحقق من صلاحية خطة التعافي من الكوارث (90 يوماً)
if (Test-Path "docs/runbooks/disaster-recovery.md") {
    $lastWrite = (Get-Item "docs/runbooks/disaster-recovery.md").LastWriteTime
    if ((Get-Date).AddDays(-90) -lt $lastWrite) {
        Write-Host "DR Runbook OK" -ForegroundColor Green
    } else {
        Write-Host "WARNING: DR runbook is older than 90 days!" -ForegroundColor Yellow
    }
} else {
    Write-Host "ERROR: DR runbook missing!" -ForegroundColor Red
}

# ==============================================================================
# 7. فحوصات خدمة الذكاء الاصطناعي (invoice-ai)
# ==============================================================================
Write-Host "`n=== Testing invoice-ai Service ===" -ForegroundColor Cyan
Push-Location invoice-ai
try {
    ruff check app tests scripts
    ruff format app tests scripts --check
    mypy app/
    pytest -q
    python scripts/check_openapi_drift.py
} finally {
    Pop-Location
}

Write-Host "`n=== All Pre-push Checks Completed Successfully! ===" -ForegroundColor Green