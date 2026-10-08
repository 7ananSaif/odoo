"""Seed five ready-to-use commercial plans ("bouquets").

A *plan* (a.k.a. "bouquet") bundles the Odoo apps a tenant may install with the
limits and pricing that go with them.  This script creates a sensible ladder of
five plans so a fresh manager has something to sell immediately.

Idempotent: every plan is matched on its ``code``, so re-running refreshes the
name, prices, limits and module list instead of creating duplicates.  Existing
plans a tenant is already subscribed to are updated in place — safe to re-run.

Usage:
    python scripts/seed_plans.py
    python scripts/seed_plans.py --currency EUR
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import create_all, session_scope  # noqa: E402
from app.models.plan import Plan, PlanModule  # noqa: E402

# Modules that always exist in a community install, used as the floor for every
# plan.  Higher tiers reference additional apps; a name that is not present on
# the target server is simply skipped when the plan is applied (see
# OdooClient.install_modules), so listing an Enterprise app here is harmless on
# a Community instance.
BASE_MODULES = ["base", "web", "contacts", "mail"]

PLANS: list[dict] = [
    {
        "code": "starter",
        "name": "Starter",
        "description": "Quotes, invoices and a shared address book for a small team.",
        "max_users": 3,
        "max_warehouses": 1,
        "max_companies": 1,
        "max_storage_mb": 5120,
        "price_month": "29",
        "price_year": "290",
        "price_extra_user": "6",
        "trial_days": 14,
        "modules": BASE_MODULES + ["sale_management", "account"],
    },
    {
        "code": "professional",
        "name": "Professional",
        "description": "Adds purchasing, inventory and a sales pipeline (CRM).",
        "max_users": 10,
        "max_warehouses": 2,
        "max_companies": 1,
        "max_storage_mb": 20480,
        "price_month": "79",
        "price_year": "790",
        "price_extra_user": "6",
        "trial_days": 14,
        "modules": BASE_MODULES + [
            "sale_management", "account", "purchase", "stock", "crm",
        ],
    },
    {
        "code": "business",
        "name": "Business",
        "description": "Manufacturing, projects and people for a growing operation.",
        "max_users": 25,
        "max_warehouses": 5,
        "max_companies": 3,
        "max_storage_mb": 51200,
        "price_month": "199",
        "price_year": "1990",
        "price_extra_user": "7",
        "trial_days": 14,
        "modules": BASE_MODULES + [
            "sale_management", "account", "purchase", "stock", "crm",
            "hr", "project", "mrp",
        ],
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "description": "The full suite, including website, e-commerce and quality.",
        "max_users": 100,
        "max_warehouses": 20,
        "max_companies": 10,
        "max_storage_mb": 204800,
        "price_month": "499",
        "price_year": "4990",
        "price_extra_user": "8",
        "trial_days": 14,
        "count_portal_users": True,
        "modules": BASE_MODULES + [
            "sale_management", "account", "purchase", "stock", "crm",
            "hr", "project", "mrp", "website", "website_sale",
            "helpdesk", "quality", "documents",
        ],
    },
    {
        "code": "reseller",
        "name": "Reseller / White-label",
        "description": "Unlimited seats and companies for partners reselling Odoo.",
        "max_users": 0,
        "max_warehouses": 50,
        "max_companies": 50,
        "max_storage_mb": 512000,
        "price_month": "899",
        "price_year": "8990",
        "price_extra_user": "0",
        "trial_days": 30,
        "count_portal_users": True,
        "modules": BASE_MODULES + [
            "sale_management", "account", "purchase", "stock", "crm",
            "hr", "project", "mrp", "website", "website_sale", "website_blog",
            "helpdesk", "quality", "documents",
        ],
    },
]

# Fields copied verbatim onto every plan (modules are handled separately).
SCALAR_FIELDS = (
    "name", "description", "active", "max_users", "max_warehouses",
    "max_companies", "max_storage_mb", "count_portal_users", "currency",
    "price_month", "price_year", "setup_fee", "price_extra_user",
    "price_extra_warehouse", "tax_rate", "trial_days",
)
DECIMAL_FIELDS = (
    "price_month", "price_year", "setup_fee", "price_extra_user",
    "price_extra_warehouse", "tax_rate",
)


def _sync_modules(plan: Plan, names: list[str]) -> None:
    """Make ``plan.modules`` contain exactly ``names`` (deduplicated)."""
    wanted: list[str] = []
    for name in names:
        if name and name not in wanted:
            wanted.append(name)
    wanted_set = set(wanted)

    for module in list(plan.modules):
        if module.technical_name not in wanted_set:
            plan.modules.remove(module)
    present = {module.technical_name for module in plan.modules}
    for name in wanted:
        if name not in present:
            plan.modules.append(PlanModule(technical_name=name))


def _upsert(session, row: dict, currency: str) -> Plan:
    plan = session.query(Plan).filter(Plan.code == row["code"]).one_or_none()
    if plan is None:
        plan = Plan(code=row["code"])
        session.add(plan)

    values = dict(row)
    values.setdefault("active", True)
    values.setdefault("count_portal_users", False)
    values.setdefault("setup_fee", "0")
    values.setdefault("price_extra_warehouse", "0")
    values.setdefault("tax_rate", "0")
    values["currency"] = currency

    for field in SCALAR_FIELDS:
        value = values[field]
        if field in DECIMAL_FIELDS:
            value = Decimal(str(value))
        setattr(plan, field, value)

    _sync_modules(plan, row["modules"])
    session.flush()
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed five commercial plans (bouquets).")
    parser.add_argument("--currency", default="USD", help="Currency for every plan (default USD)")
    args = parser.parse_args()

    currency = args.currency.strip().upper() or "USD"
    create_all()
    with session_scope() as session:
        plans = [_upsert(session, row, currency) for row in PLANS]
        rows = [
            (p.code, p.name, p.max_users, p.price_month, len(p.modules))
            for p in plans
        ]
    for code, name, max_users, price_month, module_count in rows:
        seats = max_users if max_users else "unlimited"
        print(f"  {code:<13} {name:<26} {seats:>9} seats  {price_month} {currency}/mo  {module_count} apps")
    print(f"Seeded {len(rows)} plans (currency {currency}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
