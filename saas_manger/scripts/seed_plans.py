"""Seed the commercial plan ladder ("bouquets").

A *plan* (a.k.a. "bouquet") bundles the Odoo apps a tenant may install with the
limits and pricing that go with them. This script creates a **ladder of ten
plans**, from the smallest useful set of apps to the full catalogue, so a fresh
manager has something to sell at every size.

The ladder itself lives in :mod:`app.services.app_catalogue`, which is also what
the web UI reads to answer "is this app part of a bouquet?". Two properties are
enforced there and re-checked here, because the script refuses to run on a
ladder that breaks them:

* **Monotonic** — every plan contains everything the plan below it contains, so
  upgrading a tenant never removes an app by surprise.
* **Complete** — every app in the catalogue is included by at least one plan,
  and the white-label plan (``all_apps``) authorises every app the tenant's
  database offers, so no app can ever sit outside a bouquet.

Idempotent: every plan is matched on its ``code``, so re-running refreshes the
name, prices, limits and module list instead of creating duplicates. Existing
plans a tenant is already subscribed to are updated in place — safe to re-run.

Usage:
    python scripts/seed_plans.py
    python scripts/seed_plans.py --currency EUR
    python scripts/seed_plans.py --print-catalogue   # coverage report only
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import create_all, session_scope  # noqa: E402
from app.models.plan import Plan, PlanModule  # noqa: E402
from app.services import app_catalogue  # noqa: E402


def _sync_modules(plan: Plan, names: list[str]) -> None:
    """Make ``plan.modules`` contain exactly ``names`` (deduplicated, ordered)."""
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
    values.setdefault("all_apps", False)
    values.setdefault("count_portal_users", False)
    values.setdefault("setup_fee", "0")
    values.setdefault("price_extra_warehouse", "0")
    values.setdefault("tax_rate", "0")
    values["currency"] = currency

    for field in app_catalogue.SCALAR_FIELDS:
        value = values[field]
        if field in app_catalogue.DECIMAL_FIELDS:
            value = Decimal(str(value))
        setattr(plan, field, value)

    _sync_modules(plan, row["modules"])
    session.flush()
    return plan


def _print_catalogue(rows: list[dict]) -> int:
    apps = app_catalogue.catalogue()
    base = len(app_catalogue.BASE_MODULES)
    print(f"{len(apps)} apps in the catalogue (+{base} base modules every bouquet "
          f"carries = {len(app_catalogue.known_modules())} known), {len(rows)} plans:")
    covered = app_catalogue.coverage(rows)
    for row in rows:
        wildcard = " (white-label: every app)" if row.get("all_apps") else ""
        print(f"  {row['code']:<16} {len(row['modules']):>3} apps{wildcard}")
    print("\napp coverage:")
    for name in apps:
        plans = covered.get(name, [])
        print(f"  {name:<32} {', '.join(plans) if plans else 'NOT COVERED'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the commercial plan ladder (bouquets).")
    parser.add_argument("--currency", default="USD", help="Currency for every plan (default USD)")
    parser.add_argument(
        "--print-catalogue",
        action="store_true",
        help="Print the app catalogue and the ladder coverage, then exit",
    )
    args = parser.parse_args()

    rows = app_catalogue.plan_rows()
    problems = app_catalogue.ladder_problems(rows)
    if problems:
        for problem in problems:
            print(f"ladder problem: {problem}", file=sys.stderr)
        return 1

    if args.print_catalogue:
        return _print_catalogue(rows)

    currency = args.currency.strip().upper() or "USD"
    create_all()
    with session_scope() as session:
        plans = [_upsert(session, row, currency) for row in rows]
        table = [
            (p.code, p.name, p.max_users, p.price_month, len(p.modules), p.all_apps)
            for p in plans
        ]
    for code, name, max_users, price_month, module_count, all_apps in table:
        seats = max_users if max_users else "unlimited"
        wildcard = "  (all apps)" if all_apps else ""
        print(
            f"  {code:<16} {name:<28} {seats:>9} seats  {price_month} {currency}/mo"
            f"  {module_count} apps{wildcard}"
        )
    print(
        f"Seeded {len(table)} plans covering all {len(app_catalogue.catalogue())} "
        f"catalogue apps (currency {currency})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
