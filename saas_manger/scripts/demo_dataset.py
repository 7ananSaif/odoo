"""Static fixtures for the optional demo dataset.

Pure data — no database access, no imports from ``app``. ``scripts/seed_demo.py``
turns these rows into database records.

Date-dependent values are stored as *offsets in days from "today"* so the demo
stays meaningful whenever it is (re-)seeded: Acme is about to expire, Beta is
mid-trial, Gamma is already cancelled.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

CURRENCY = "USD"
TAX_RATE = Decimal("0.1900")


def offset(days: int) -> date:
    """Return the date ``days`` away from today (negative = past)."""
    return date.today() + timedelta(days=days)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------
PLANS: list[dict] = [
    {
        "code": "standard",
        "name": "Standard",
        "description": "Sales, invoicing and inventory for a single-company business.",
        "active": True,
        "max_users": 5,
        "max_warehouses": 1,
        "max_companies": 1,
        "max_storage_mb": 5120,
        "count_portal_users": False,
        "currency": CURRENCY,
        "price_month": Decimal("150.00"),
        "price_year": Decimal("1500.00"),
        "setup_fee": Decimal("0.00"),
        "price_extra_user": Decimal("15.00"),
        "price_extra_warehouse": Decimal("25.00"),
        "tax_rate": TAX_RATE,
        "trial_days": 14,
        "modules": ["account", "base", "sale_management", "stock", "web"],
    },
    {
        "code": "premium",
        "name": "Premium",
        "description": "Full suite: sales, purchase, manufacturing and multi-warehouse.",
        "active": True,
        "max_users": 25,
        "max_warehouses": 4,
        "max_companies": 3,
        "max_storage_mb": 25600,
        "count_portal_users": True,
        "currency": CURRENCY,
        "price_month": Decimal("350.00"),
        "price_year": Decimal("3500.00"),
        "setup_fee": Decimal("250.00"),
        "price_extra_user": Decimal("20.00"),
        "price_extra_warehouse": Decimal("30.00"),
        "tax_rate": TAX_RATE,
        "trial_days": 21,
        "modules": [
            "account",
            "base",
            "mrp",
            "purchase",
            "sale_management",
            "stock",
            "web",
        ],
    },
]


# ---------------------------------------------------------------------------
# Tenants — ``key`` is the join key used by subscriptions/invoices/payments.
# ---------------------------------------------------------------------------
TENANTS: list[dict] = [
    {
        "key": "acme",
        "name": "Acme Inc",
        "subdomain": "acme",
        "db_name": "acme",
        "contact_name": "Dana Whitfield",
        "email": "billing@acme.test",
        "phone": "+1 555 0100",
        "country": "United States",
        "tax_id": "US-1234567",
        "notes": "Demo tenant — active subscription, invoice partly paid.",
        "plan_code": "standard",
        "status": "active",
        "start_offset_days": -370,
        "expiry_offset_days": 10,
        "auto_renew": True,
        "current_users": 4,
        "current_warehouses": 1,
        "current_companies": 1,
        "current_storage_mb": Decimal("1830.50"),
        "count_portal_users": False,
        "block_writes": True,
        "provisioned": True,
    },
    {
        "key": "beta",
        "name": "Beta Ltd",
        "subdomain": "beta",
        "db_name": "beta",
        "contact_name": "Sam Okafor",
        "email": "accounts@beta.test",
        "phone": "+44 20 7946 0100",
        "country": "United Kingdom",
        "tax_id": "GB-7654321",
        "notes": "Demo tenant — trial on the premium plan with an overdue invoice.",
        "plan_code": "premium",
        "status": "trial",
        "start_offset_days": -25,
        "expiry_offset_days": 60,
        "auto_renew": True,
        "current_users": 6,
        "current_warehouses": 1,
        "current_companies": 1,
        "current_storage_mb": Decimal("604.25"),
        "count_portal_users": True,
        "block_writes": True,
        "provisioned": True,
    },
    {
        "key": "gamma",
        "name": "Gamma Retail",
        "subdomain": "gamma",
        "db_name": "gamma",
        "contact_name": "Lena Fischer",
        "email": "finance@gamma.test",
        "phone": "+49 30 1234567",
        "country": "Germany",
        "tax_id": "DE-123456789",
        "notes": "Demo tenant — cancelled; counts towards churn.",
        "plan_code": "standard",
        "status": "cancelled",
        "start_offset_days": -400,
        "expiry_offset_days": -40,
        "auto_renew": False,
        "current_users": 1,
        "current_warehouses": 0,
        "current_companies": 1,
        "current_storage_mb": Decimal("212.00"),
        "count_portal_users": False,
        "block_writes": True,
        "provisioned": True,
    },
]


# ---------------------------------------------------------------------------
# Subscriptions (one per tenant, joined by tenant key)
# ---------------------------------------------------------------------------
SUBSCRIPTIONS: list[dict] = [
    {
        "tenant_key": "acme",
        "cycle": "monthly",
        "status": "active",
        "next_invoice_offset_days": 10,
        "payment_terms_days": 15,
        "auto_renew": True,
        "notes": "Demo subscription — billed monthly.",
    },
    {
        "tenant_key": "beta",
        "cycle": "yearly",
        "status": "trial",
        "next_invoice_offset_days": 60,
        "payment_terms_days": 30,
        "auto_renew": True,
        "notes": "Demo subscription — annual billing after the trial.",
    },
    {
        "tenant_key": "gamma",
        "cycle": "monthly",
        "status": "cancelled",
        "next_invoice_offset_days": None,
        "payment_terms_days": 15,
        "auto_renew": False,
        "notes": "Demo subscription — cancelled.",
    },
]


# ---------------------------------------------------------------------------
# Invoices + their lines
# ---------------------------------------------------------------------------
INVOICES: list[dict] = [
    {
        "number": "INV-000001",
        "tenant_key": "acme",
        "status": "sent",
        "issue_offset_days": -20,
        "due_offset_days": -5,
        "period_start_offset_days": -20,
        "period_end_offset_days": 10,
        "subtotal": Decimal("150.00"),
        "tax_total": Decimal("28.50"),
        "total": Decimal("178.50"),
        "amount_paid": Decimal("40.00"),
        "notes": "Demo invoice — partly paid, balance outstanding.",
        "lines": [
            {
                "description": "Standard plan — monthly subscription",
                "quantity": Decimal("1.00"),
                "unit_price": Decimal("150.00"),
                "line_total": Decimal("150.00"),
            }
        ],
    },
    {
        "number": "INV-000002",
        "tenant_key": "beta",
        "status": "overdue",
        "issue_offset_days": -45,
        "due_offset_days": -30,
        "period_start_offset_days": -45,
        "period_end_offset_days": 320,
        "subtotal": Decimal("2500.00"),
        "tax_total": Decimal("475.00"),
        "total": Decimal("2975.00"),
        "amount_paid": Decimal("0.00"),
        "notes": "Demo invoice — overdue annual subscription.",
        "lines": [
            {
                "description": "Premium plan — annual subscription",
                "quantity": Decimal("1.00"),
                "unit_price": Decimal("2250.00"),
                "line_total": Decimal("2250.00"),
            },
            {
                "description": "Setup fee",
                "quantity": Decimal("1.00"),
                "unit_price": Decimal("250.00"),
                "line_total": Decimal("250.00"),
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
PAYMENTS: list[dict] = [
    {
        "tenant_key": "acme",
        "invoice_number": "INV-000001",
        "date_offset_days": -18,
        "amount": Decimal("40.00"),
        "method": "bank_transfer",
        "kind": "payment",
        "reference": "WIRE-889201",
        "notes": "Demo payment — part settlement of INV-000001.",
    },
]
