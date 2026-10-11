# SaaS Manager

A standalone control plane for **multi-tenant Odoo** (one database per client),
plus a small **core patch** that locks app and database management inside each
client database.

Two deliverables live in this repository:

| Deliverable | Where | What it is |
|---|---|---|
| **Part 1 — Core lock** | `patch/` | A `.patch` for the Odoo 19 source that blocks app install/uninstall/upgrade, the database manager, the Apps/Technical menus and developer mode inside client databases, and enforces per-tenant plan limits. |
| **Part 2 — SaaS Manager** | `app/` | A FastAPI + Celery + Redis + Jinja2 application that provisions and manages tenants, plans, limits, updates, backups and billing. |

---

## 1. What the core patch does

Applied to `D:\odoo\odoo`, the patch adds one helper module
(`odoo/tools/saas_lock.py`, every line marked `# SAAS-PATCH`) that all other
edits call. Switches live in `odoo.conf`:

```ini
[options]
saas_lock = True
saas_manager_token = <a long random secret>
```

With the lock on:

* **No app management from the client** — `ir.module.module` install/uninstall/
  upgrade/update-list raise `AccessError` unless the call carries the manager
  token (HTTP header `X-Saas-Manager-Token`, RPC `context.saas_manager_token`,
  or a CLI `-i`/`-u` run by the owner).
* **No database management from the client** — `/web/database/*`, the `db`
  service and `/xmlrpc/2/db` are refused (create/duplicate/drop/backup/restore/
  list/change-master-password) unless authorised by the token. The guard runs
  *before* the master password is checked, so even the master password cannot
  bypass it.
* **Hidden Apps and Technical menus**, developer mode disabled for clients.
* **Plan limits enforced inside the client DB** — `res.users`, `res.company`,
  `stock.warehouse` and `ir.attachment` check `saas.max_users`,
  `saas.max_companies`, `saas.max_warehouses`, `saas.max_storage_mb` and raise a
  clear `UserError` when the limit is reached.
* **`saas.*` parameters are invisible and immutable to clients** — only the
  manager can read or write them.
* **Suspended / expired tenants** become read-only automatically.

See [`patch/APPLY_WINDOWS.md`](patch/APPLY_WINDOWS.md) for the exact apply steps
and [`docs/TESTING.md`](docs/TESTING.md) for the proof tests.

---

## 2. What the SaaS Manager does

* **Tenants** — one database + subdomain per client. Identity, plan, status
  (trial/active/suspended/expired/cancelled), start/expiry dates, auto-renew,
  and per-tenant limit **overrides**. Buttons to *push limits*, *refresh usage*,
  *backup*, *restore*, *suspend*, *activate*, *duplicate*, *delete*.
* **Plans ("bouquets")** — allowed Odoo modules, default limits and full pricing
  (monthly, yearly, setup fee, price per extra user/warehouse, tax, currency,
  trial days). Changing a tenant's plan installs/removes apps automatically and
  pushes the new limits. **Downgrades are blocked** when current usage exceeds
  the new limits, listing exactly what must be reduced.
* **Usage** — refreshed by a Celery beat schedule: users, warehouses, companies,
  storage, database size, last login, last backup. Alerts at 80% and 100% of any
  limit.
* **Updates** — register versions, then run batch updates over all/selected
  databases. Every job: optional maintenance mode → **backup first** → run
  `odoo-bin -u ... --stop-after-init` → on failure **automatic rollback** from
  the pre-update backup. Per-database status and streamed logs.
* **Finance** — subscriptions, automatic invoice generation (plan price + extra
  users/warehouses + setup fee − discount + tax), payments, **deposits** and
  **refunds**, **credit and debit notes**, per-tenant balances, dunning
  (reminders before expiry and after an overdue due date, auto-suspend after a
  configurable grace period, auto-reactivation on payment), a financial settings
  page, PDF invoices, **invoice emailing**, MRR / yearly revenue / outstanding /
  overdue / revenue-per-plan / **churn** / **expiring-subscription** reporting,
  and Excel/CSV export.
* **Security** — single owner account, Argon2 passwords, TOTP 2FA, signed
  sessions, rate-limited login, Fernet-encrypted secrets at rest, and a
  **complete audit log** of every action.

---

## 3. Quick start (Windows)

```powershell
# 1. Python environment
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Configure
copy .env.example .env
#    edit .env: SECRET_KEY, SECRETS_KEY, MANAGER_DB_URL, ODOO_* ...

# 3. Create the manager database + the owner account
venv\Scripts\python.exe scripts\init_db.py
venv\Scripts\python.exe scripts\create_owner.py --email owner@example.com --name "Owner"

# 4. Apply the core patch to Odoo and set the two odoo.conf keys
#    (see patch\APPLY_WINDOWS.md)

# 5. Run the web app and the workers (three terminals) — or install services:
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8080
venv\Scripts\python.exe -m celery -A app.workers.celery_app.celery_app worker --loglevel=INFO --pool=solo -Q default,updates,backups
venv\Scripts\python.exe -m celery -A app.workers.celery_app.celery_app beat --loglevel=INFO

# ... or as Windows services (needs NSSM, run as Administrator):
powershell -ExecutionPolicy Bypass -File scripts\install_services.ps1
```

Open <http://localhost:8080>, sign in, enroll 2FA, then create a plan and a
tenant.

Full instructions: [`docs/INSTALL.md`](docs/INSTALL.md).

---

## 4. Repository layout

```
saas_manger/
├── app/
│   ├── main.py              FastAPI app + routers + middleware
│   ├── config.py            typed settings (.env)
│   ├── db.py                engine, session, Base
│   ├── security.py          Argon2, TOTP, Fernet, signed sessions
│   ├── deps.py              auth dependencies
│   ├── models/              SQLAlchemy models (users, plans, tenants, ops, billing)
│   ├── services/            business logic (odoo client, pg tools, provisioner,
│   │                        plans, limits, usage, backups, updates, billing,
│   │                        invoice PDF, outgoing email)
│   ├── workers/             Celery app + tasks + beat schedule
│   ├── web/                 routes (auth, dashboard, tenants, plans, updates,
│   │                        finance, settings, audit) + Jinja env
│   ├── templates/           Jinja2 templates
│   └── static/              CSS + favicon
├── patch/                   Part 1: the Odoo core lock
│   ├── saas_manager_lock.patch
│   ├── odoo.conf.snippet
│   └── APPLY_WINDOWS.md
├── scripts/                 init_db, create_owner, NSSM installer
├── tests/                   pytest suite
└── docs/                    INSTALL, TESTING, ARCHITECTURE
```

---

## 5. Documentation

* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how the pieces fit together.
* [`docs/INSTALL.md`](docs/INSTALL.md) — full Windows install, NSSM services,
  nginx/TLS notes.
* [`docs/TESTING.md`](docs/TESTING.md) — the full test checklist, including the
  manual verification that a client admin cannot bypass the lock.
* [`patch/APPLY_WINDOWS.md`](patch/APPLY_WINDOWS.md) — applying the core patch.
