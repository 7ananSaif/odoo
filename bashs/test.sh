python .\odoo-bin -c odoo.conf -d test_db -i invoice_agent --test-enable --stop-after-init --log-level=test
python .\odoo-bin -c odoo.conf -d test_db -u invoice_agent --test-enable --stop-after-init --log-handler odoo.tools.convert:DEBUG
python .\odoo-bin -c odoo.conf -d test_db -i invoice_agent --test-enable --stop-after-init --log-level=test
pip install asyncpg anyio httpx pytest-anyio pytest-asyncio
Collecting asyncpg
o> python -m pytest invoice-ai/tests -q -m "not slow"
# فحص تنسيق الكود مع Ruff
ruff check invoice-ai --config pyproject.toml
ruff format invoice-ai --config pyproject.toml --check

# فحص الثغرات الأمنية في كود Python مع Bandit
bandit -r invoice-ai/ -ll --severity-level medium

python -m pytest invoice-ai/tests -q -m "not slow"
 python -m pytest invoice-ai/tests -q -m "not slow"

# تشغيل اختبارات Odoo والتغطية (Coverage)
coverage run --concurrency=thread --source=custom_addons/invoice_agent ./odoo-bin -d test_db -i invoice_agent --test-enable --test-tags /invoice_agent --stop-after-init

# عرض نسبة تغطية الاختبارات (يجب أن تكون 60% أو أعلى)
coverage report -m ء



# التأكد من تنسيق ملفات Terraform
terraform -chdir=infra/terraform/ fmt -check -recursive

# تهيئة بيئة الاختبار المحلية
terraform -chdir=infra/terraform/ init -backend=false

# التحقق من صحة القواعد والـ Syntax
terraform -chdir=infra/terraform/ validate


# فحص صحة إعدادات Prometheus
docker run --rm -v "$(pwd)/infra/observability/prometheus:/etc/prometheus" prom/prometheus:v2.53.0 checkconfig /etc/prometheus/prometheus.yml

# فحص صحة إعدادات Alertmanager
docker run --rm -v "$(pwd)/infra/observability/alertmanager:/etc/alertmanager" prom/alertmanager:v0.27.0 checkconfig /etc/alertmanager/alertmanager.yml

# التحقق من صحة ملف JSON الخاص بـ Grafana Dashboard
python3 -c "import json; json.load(open('infra/observability/grafana/dashboards/agent-slo.json'))"


# فحص ثغرات الملفات والمكتبات في المشروع
trivy fs --severity CRITICAL,HIGH .

# بناء الحاوية محلياً وفحص ثغرات الـ Image
docker build -t odoo-test:local .
trivy image --severity CRITICAL,HIGH odoo-test:local

# التحقق من وجود وتحديث خطة التعافي من الكوارث (آخر 90 يوم)
test -f docs/runbooks/disaster-recovery.md && [ $(expr $(date +%s) - $(stat -c %Y docs/runbooks/disaster-recovery.md)) -lt 7776000 ] && echo "DR Runbook OK"


cd invoice-ai

# فحص التنسيق والأخطاء الهيكلية
ruff check app tests scripts
ruff format app tests scripts --check

# فحص الأنواع (Type Checking)
mypy app/

# تشغيل اختبارات Pytest
pytest -q

# فحص التغير في الـ API (OpenAPI Drift Check)
python scripts/check_openapi_drift.py

docker run --rm `
  -e HOST=host.docker.internal `
  -e PORT=5433 `
  -e USER=openpg `
  -e PASSWORD=your_password `
  -v d:\odoo\odoo\custom_addons:/mnt/extra-addons `
  odoo:19.0 `
  -- `
  -d test_db `
  -i invoice_agent `
  --test-tags /invoice_agent `
  --stop-after-init `
  --log-level=test