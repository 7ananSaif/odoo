"""Seed (or purge) a small, realistic demo dataset in the manager database.

Idempotent: every row is matched on its natural key (plan code, tenant
subdomain, invoice number, payment reference), so re-running refreshes the
demo records instead of duplicating them.

Usage:
    python scripts/seed_demo.py            # create or refresh the demo data
    python scripts/seed_demo.py --purge    # remove ONLY the demo records

The fixtures themselves live in ``scripts/demo_dataset.py``.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))  # project root, so `app` is importable
sys.path.insert(0, str(_HERE))         # sibling fixtures module

import demo_dataset as demo  # noqa: E402
from app.db import create_all, session_scope  # noqa: E402
from app.models.billing import Invoice, InvoiceLine, Payment, Subscription  # noqa: E402
from app.models.plan import Plan, PlanModule  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402

PLAN_FIELDS = (
    "name", "description", "active", "max_users", "max_warehouses", "max_companies",
    "max_storage_mb", "count_portal_users", "currency", "price_month", "price_year",
    "setup_fee", "price_extra_user", "price_extra_warehouse", "tax_rate", "trial_days",
)
TENANT_FIELDS = (
    "name", "contact_name", "email", "phone", "country", "tax_id", "notes", "status",
    "auto_renew", "current_users", "current_warehouses", "current_companies",
    "current_storage_mb", "count_portal_users", "block_writes", "provisioned",
)


def _shift(today: date, days: int) -> date:
    """Return ``today`` shifted by ``days`` (negative = past)."""
    return today + timedelta(days=days)


def _sync_modules(plan: Plan, names: list[str]) -> None:
    """Make ``plan.modules`` contain exactly ``names``."""
    wanted = set(names)
    for module in list(plan.modules):
        if module.technical_name not in wanted:
            plan.modules.remove(module)
    present = {module.technical_name for module in plan.modules}
    for name in sorted(wanted - present):
        plan.modules.append(PlanModule(technical_name=name))


def _upsert_plan(session, row: dict) -> Plan:
    plan = session.query(Plan).filter(Plan.code == row["code"]).one_or_none()
    if plan is None:
        plan = Plan(code=row["code"])
        session.add(plan)
    for field in PLAN_FIELDS:
        setattr(plan, field, row[field])
    _sync_modules(plan, row["modules"])
    session.flush()
    return plan


def _upsert_tenant(session, row: dict, plans: dict[str, Plan], today: date) -> Tenant:
    tenant = session.query(Tenant).filter(Tenant.subdomain == row["subdomain"]).one_or_none()
    if tenant is None:
        tenant = Tenant(subdomain=row["subdomain"], db_name=row["db_name"])
        session.add(tenant)
    plan = plans[row["plan_code"]]
    for field in TENANT_FIELDS:
        setattr(tenant, field, row[field])
    tenant.plan_id = plan.id
    tenant.trial_days = plan.trial_days
    tenant.start_date = _shift(today, row["start_offset_days"])
    tenant.expiry_date = _shift(today, row["expiry_offset_days"])
    # Limits are copied from the plan; the demo does not override them.
    tenant.max_users = plan.max_users
    tenant.max_warehouses = plan.max_warehouses
    tenant.max_companies = plan.max_companies
    tenant.max_storage_mb = plan.max_storage_mb
    session.flush()
    return tenant


def _upsert_subscription(session, row: dict, tenant: Tenant, plan: Plan, today: date) -> Subscription:
    sub = session.query(Subscription).filter(Subscription.tenant_id == tenant.id).one_or_none()
    if sub is None:
        sub = Subscription(tenant_id=tenant.id)
        session.add(sub)
    sub.plan_id = plan.id
    sub.cycle = row["cycle"]
    sub.status = row["status"]
    sub.start_date = tenant.start_date
    if row["next_invoice_offset_days"] is None:
        sub.next_invoice_date = None
    else:
        sub.next_invoice_date = _shift(today, row["next_invoice_offset_days"])
    sub.currency = plan.currency
    sub.tax_rate = plan.tax_rate
    sub.payment_terms_days = row["payment_terms_days"]
    sub.auto_renew = row["auto_renew"]
    sub.notes = row["notes"]
    session.flush()
    return sub


def _upsert_invoice(session, row: dict, tenant: Tenant, sub: Subscription, today: date) -> Invoice:
    invoice = session.query(Invoice).filter(Invoice.number == row["number"]).one_or_none()
    if invoice is None:
        invoice = Invoice(number=row["number"])
        session.add(invoice)
    invoice.tenant_id = tenant.id
    invoice.subscription_id = sub.id
    invoice.status = row["status"]
    invoice.issue_date = _shift(today, row["issue_offset_days"])
    invoice.due_date = _shift(today, row["due_offset_days"])
    invoice.period_start = _shift(today, row["period_start_offset_days"])
    invoice.period_end = _shift(today, row["period_end_offset_days"])
    invoice.currency = tenant.plan.currency
    invoice.subtotal = row["subtotal"]
    invoice.tax_total = row["tax_total"]
    invoice.total = row["total"]
    invoice.amount_paid = row["amount_paid"]
    invoice.notes = row["notes"]
    invoice.lines.clear()
    for line in row["lines"]:
        invoice.lines.append(InvoiceLine(
            description=line["description"],
            quantity=line["quantity"],
            unit_price=line["unit_price"],
            tax_rate=demo.TAX_RATE,
            line_total=line["line_total"],
        ))
    session.flush()
    return invoice


def _upsert_payment(session, row: dict, tenant: Tenant, invoices: dict[str, Invoice], today: date) -> Payment:
    payment = session.query(Payment).filter(Payment.reference == row["reference"]).one_or_none()
    if payment is None:
        payment = Payment(reference=row["reference"])
        session.add(payment)
    payment.tenant_id = tenant.id
    payment.invoice_id = invoices[row["invoice_number"]].id
    payment.date = _shift(today, row["date_offset_days"])
    payment.amount = row["amount"]
    payment.currency = tenant.plan.currency
    payment.method = row["method"]
    payment.kind = row["kind"]
    payment.notes = row["notes"]
    session.flush()
    return payment


def seed(session) -> None:
    """Create or refresh the whole demo dataset."""
    today = date.today()
    plans = {row["code"]: _upsert_plan(session, row) for row in demo.PLANS}

    tenants: dict[str, Tenant] = {}
    for row in demo.TENANTS:
        tenants[row["key"]] = _upsert_tenant(session, row, plans, today)

    subs: dict[int, Subscription] = {}
    for row in demo.SUBSCRIPTIONS:
        tenant = tenants[row["tenant_key"]]
        subs[tenant.id] = _upsert_subscription(session, row, tenant, plans[tenant.plan.code], today)

    invoices: dict[str, Invoice] = {}
    for row in demo.INVOICES:
        tenant = tenants[row["tenant_key"]]
        invoices[row["number"]] = _upsert_invoice(session, row, tenant, subs[tenant.id], today)

    for row in demo.PAYMENTS:
        _upsert_payment(session, row, tenants[row["tenant_key"]], invoices, today)

    print(
        f"Seeded {len(plans)} plans, {len(tenants)} tenants, {len(subs)} subscriptions, "
        f"{len(invoices)} invoices, {len(demo.PAYMENTS)} payments."
    )


def purge(session) -> None:
    """Delete the demo records (matched on the same natural keys)."""
    subdomains = [row["subdomain"] for row in demo.TENANTS]
    tenant_ids = [tid for (tid,) in session.query(Tenant.id).filter(Tenant.subdomain.in_(subdomains))]
    if tenant_ids:
        session.query(Payment).filter(Payment.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        session.query(Invoice).filter(Invoice.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        session.query(Subscription).filter(Subscription.tenant_id.in_(tenant_ids)).delete(synchronize_session=False)
        session.query(Tenant).filter(Tenant.id.in_(tenant_ids)).delete(synchronize_session=False)
    codes = [row["code"] for row in demo.PLANS]
    session.query(Plan).filter(Plan.code.in_(codes)).delete(synchronize_session=False)
    print(f"Purged {len(tenant_ids)} demo tenants and {len(codes)} demo plans.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed or purge the demo dataset.")
    parser.add_argument("--purge", action="store_true", help="delete the demo records instead of creating them")
    args = parser.parse_args()

    create_all()
    with session_scope() as session:
        if args.purge:
            purge(session)
        else:
            seed(session)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
