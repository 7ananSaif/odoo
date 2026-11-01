"""The catalogue of Odoo apps the manager sells, and the ladder of bouquets.

This module is the **single source of truth** for three things:

* which apps exist — the *catalogue*;
* which plan ("bouquet") introduces each one — the *ladder*;
* whether the ladder actually covers the whole catalogue.

The rule the product needs is "every app is part of a bouquet": an app that no
bouquet lists could never be installed through the manager, so the ladder is
built so that (a) tiers are cumulative — upgrading a tenant never removes an
app — and (b) the last tier authorises the entire catalogue, and more: it is a
*white-label* plan (``all_apps``) that allows any app present in the tenant's
database, including apps added after this file was written.

:func:`coverage` and :func:`uncovered` are used by the seeder (which refuses to
run on an incomplete ladder) and by the coverage screen in the web UI.

Nothing here imports the rest of the application, so it is safe to import from
a CLI script before the database engine exists.
"""
from __future__ import annotations

#: Modules the manager must never uninstall, whatever a plan says. Every plan
#: gets them, including a plan with an empty module list.
ALWAYS_KEEP = frozenset({"base", "web"})

#: Modules every bouquet carries on top of its own apps. ``saas_tenant_guard``
#: rides along on purpose: it is what hides Odoo's own Apps (module installer)
#: menu inside the tenant and enforces the seat limit, so a tenant without it
#: could install apps by itself.
BASE_MODULES: tuple[str, ...] = (
    "base", "web", "contacts", "mail", "saas_tenant_guard",
)

#: The ladder, cheapest first. Each tier lists the apps it *introduces*; a plan
#: owns everything the tiers below it own plus its own (see :func:`tier_modules`).
#: The special key ``"all_apps": True`` on the last tier marks the plan as
#: white-label: it authorises every app, not only the ones listed here.
TIER_APPS: tuple[dict, ...] = (
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
        "apps": ["sale_management", "account"],
    },
    {
        "code": "essentials",
        "name": "Essentials",
        "description": "Buying and inventory on top of the sales core.",
        "max_users": 5,
        "max_warehouses": 2,
        "max_companies": 1,
        "max_storage_mb": 10240,
        "price_month": "49",
        "price_year": "490",
        "price_extra_user": "6",
        "trial_days": 14,
        "apps": ["purchase", "stock"],
    },
    {
        "code": "professional",
        "name": "Professional",
        "description": "Adds the sales pipeline and project delivery.",
        "max_users": 10,
        "max_warehouses": 2,
        "max_companies": 1,
        "max_storage_mb": 20480,
        "price_month": "79",
        "price_year": "790",
        "price_extra_user": "6",
        "trial_days": 14,
        "apps": ["crm", "project", "calendar", "crm_dashboard"],
    },
    {
        "code": "business",
        "name": "Business",
        "description": "People, expenses and time off for a growing team.",
        "max_users": 15,
        "max_warehouses": 3,
        "max_companies": 2,
        "max_storage_mb": 40960,
        "price_month": "129",
        "price_year": "1290",
        "price_extra_user": "7",
        "trial_days": 14,
        "apps": ["hr", "hr_expense", "hr_holidays", "hr_attendance"],
    },
    {
        "code": "growth",
        "name": "Growth",
        "description": "Manufacturing, quality and maintenance for a real operation.",
        "max_users": 20,
        "max_warehouses": 4,
        "max_companies": 2,
        "max_storage_mb": 51200,
        "price_month": "179",
        "price_year": "1790",
        "price_extra_user": "7",
        "trial_days": 14,
        "apps": ["mrp", "quality_control", "maintenance", "repair", "stock_barcode"],
    },
    {
        "code": "advanced",
        "name": "Advanced",
        "description": "Website, marketing and surveys to win new customers.",
        "max_users": 25,
        "max_warehouses": 5,
        "max_companies": 3,
        "max_storage_mb": 76800,
        "price_month": "229",
        "price_year": "2290",
        "price_extra_user": "7",
        "trial_days": 14,
        "apps": [
            "website", "mass_mailing", "mass_mailing_sms", "survey",
            "marketing_automation", "social", "website_event",
        ],
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "description": "eCommerce, point of sale, subscriptions and helpdesk.",
        "max_users": 50,
        "max_warehouses": 10,
        "max_companies": 5,
        "max_storage_mb": 102400,
        "price_month": "349",
        "price_year": "3490",
        "price_extra_user": "8",
        "trial_days": 14,
        "count_portal_users": True,
        "apps": [
            "website_sale", "point_of_sale", "pos_restaurant", "sale_subscription",
            "helpdesk", "accountant", "account_reports", "sale_amazon",
        ],
    },
    {
        "code": "enterprise_plus",
        "name": "Enterprise Plus",
        "description": "Knowledge, sign, planning, timesheets and field service.",
        "max_users": 75,
        "max_warehouses": 15,
        "max_companies": 8,
        "max_storage_mb": 153600,
        "price_month": "449",
        "price_year": "4490",
        "price_extra_user": "8",
        "trial_days": 14,
        "count_portal_users": True,
        "apps": [
            "knowledge", "sign", "planning", "timesheet_grid", "industry_fsm",
            "appointment", "hr_recruitment", "website_hr_recruitment",
            "hr_appraisal", "hr_skills", "lunch", "fleet", "voip", "im_livechat",
        ],
    },
    {
        "code": "complete",
        "name": "Complete",
        "description": "The full standard suite, including the advanced manufacturing add-ons.",
        "max_users": 100,
        "max_warehouses": 20,
        "max_companies": 10,
        "max_storage_mb": 204800,
        "price_month": "649",
        "price_year": "6490",
        "price_extra_user": "8",
        "trial_days": 14,
        "count_portal_users": True,
        "apps": [
            "mrp_workorder", "mrp_plm", "website_slides", "website_blog",
            "project_todo", "data_recycle", "marketing_card", "web_mobile",
        ],
    },
    {
        "code": "everything",
        "name": "Everything (white-label)",
        "description": (
            "Unlimited seats and every app in the catalogue — nothing is left out, "
            "including site-specific and locally developed apps."
        ),
        "max_users": 0,
        "max_warehouses": 50,
        "max_companies": 50,
        "max_storage_mb": 512000,
        "price_month": "899",
        "price_year": "8990",
        "price_extra_user": "0",
        "trial_days": 30,
        "count_portal_users": True,
        # White-label: authorises every app the tenant's database offers, not
        # only the names listed below, so no app can ever be left outside a
        # bouquet.
        "all_apps": True,
        "apps": None,  # None → every app in the catalogue (see tier_modules)
    },
)

#: Applications only the white-label plan is expected to introduce explicitly:
#: provider-side, site-specific or locally developed apps. Kept apart from the
#: tiers because they are not part of the standard commercial ladder.
CATALOGUE_TAIL: tuple[str, ...] = (
    "saas_manager", "web_studio", "l10n_sa_zatca_compliance", "hotel", "library",
)


def catalogue() -> list[str]:
    """Every app the ladder covers, in the order the tiers introduce them."""
    names: list[str] = []
    for tier in TIER_APPS:
        for name in tier["apps"] or []:
            if name not in names:
                names.append(name)
    for name in CATALOGUE_TAIL:
        if name not in names:
            names.append(name)
    return names


def catalogue_set() -> frozenset[str]:
    """The catalogue as a set, for membership tests."""
    return frozenset(catalogue())


def known_modules() -> list[str]:
    """Every module the manager knows: the catalogue plus the shared base.

    The catalogue is what the tiers introduce; ``BASE_MODULES`` (``base``,
    ``web``, ``contacts``, ``mail``, ``saas_tenant_guard``) ride on *every*
    bouquet, so they belong to the same inventory the coverage screen reports.
    """
    names = catalogue()
    for name in BASE_MODULES:
        if name not in names:
            names.append(name)
    return names


def known_set() -> frozenset[str]:
    """``known_modules`` as a set, for membership tests."""
    return frozenset(known_modules())


def tier_modules(index: int) -> list[str]:
    """The modules of tier ``index`` (0-based): every tier below plus its own."""
    modules: list[str] = []
    for tier in TIER_APPS[: index + 1]:
        for name in tier["apps"] if tier["apps"] is not None else catalogue():
            if name not in modules:
                modules.append(name)
    for name in BASE_MODULES:
        if name not in modules:
            modules.append(name)
    return ["base"] + [name for name in modules if name != "base"]


#: Fields the seeder copies verbatim onto a plan row (modules are separate).
SCALAR_FIELDS: tuple[str, ...] = (
    "name", "description", "active", "all_apps", "max_users", "max_warehouses",
    "max_companies", "max_storage_mb", "count_portal_users", "currency",
    "price_month", "price_year", "setup_fee", "price_extra_user",
    "price_extra_warehouse", "tax_rate", "trial_days",
)

#: Fields in :data:`SCALAR_FIELDS` that must be coerced to ``Decimal``.
DECIMAL_FIELDS: tuple[str, ...] = (
    "price_month", "price_year", "setup_fee", "price_extra_user",
    "price_extra_warehouse", "tax_rate",
)


def plan_rows() -> list[dict]:
    """One dict per plan: its tier settings plus its cumulative module list."""
    rows: list[dict] = []
    for index, tier in enumerate(TIER_APPS):
        row = dict(tier)
        row.pop("apps", None)
        row.setdefault("all_apps", False)
        row.setdefault("active", True)
        row.setdefault("count_portal_users", False)
        row["modules"] = tier_modules(index)
        rows.append(row)
    return rows


def coverage(rows: list[dict] | None = None) -> dict[str, list[str]]:
    """Map every catalogued app to the plan codes that include it."""
    covered: dict[str, list[str]] = {}
    for row in rows if rows is not None else plan_rows():
        for name in row["modules"]:
            covered.setdefault(name, []).append(row["code"])
    return covered


def uncovered(rows: list[dict] | None = None) -> list[str]:
    """Catalogued apps that no plan includes — must be empty."""
    covered = coverage(rows)
    return [name for name in catalogue() if name not in covered]


def ladder_problems(rows: list[dict] | None = None) -> list[str]:
    """Every reason the ladder is not complete and monotonic.

    * **Monotonic** — a plan that is missing something the plan below it has
      would remove an app from a tenant that simply upgrades.
    * **Complete** — every app in the catalogue is included by at least one
      plan, so no app can be impossible to install.

    An empty list means the ladder is sound. The seeder refuses to run
    otherwise, and the coverage screen shows the same verdict.
    """
    rows = rows if rows is not None else plan_rows()
    problems: list[str] = []
    previous: set[str] = set()
    for row in rows:
        modules = set(row["modules"])
        missing = previous - modules
        if missing:
            problems.append(
                f"{row['code']} is missing {sorted(missing)} that the plan below it has"
            )
        previous = modules
    missing_apps = uncovered(rows)
    if missing_apps:
        problems.append(f"no plan includes {missing_apps}")
    return problems


__all__ = [
    "ALWAYS_KEEP",
    "BASE_MODULES",
    "CATALOGUE_TAIL",
    "DECIMAL_FIELDS",
    "SCALAR_FIELDS",
    "TIER_APPS",
    "catalogue",
    "catalogue_set",
    "coverage",
    "known_modules",
    "known_set",
    "ladder_problems",
    "plan_rows",
    "tier_modules",
    "uncovered",
]
