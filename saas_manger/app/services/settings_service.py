"""Read/write access to the configurable settings, with typed helpers."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings as env
from app.models.settings import (
    S_AUTO_REACTIVATE,
    S_AUTO_SUSPEND,
    S_BANK_DETAILS,
    S_COMPANY_ADDRESS,
    S_COMPANY_EMAIL,
    S_COMPANY_LOGO,
    S_COMPANY_NAME,
    S_COMPANY_PHONE,
    S_COMPANY_TAX_ID,
    S_DEFAULT_CURRENCY,
    S_DEFAULT_TAX_RATE,
    S_DUNNING_ENABLED,
    S_GRACE_DAYS,
    S_INVOICE_NEXT_NUMBER,
    S_INVOICE_PREFIX,
    S_LATE_FEE_PERCENT,
    S_PAYMENT_METHODS,
    S_REMINDER_DAYS_AFTER,
    S_REMINDER_DAYS_BEFORE,
    S_TRIAL_DAYS,
    Setting,
)

# Default values seeded on first run. (key, value, description)
DEFAULTS: list[tuple[str, str, str]] = [
    (S_COMPANY_NAME, "My SaaS Company", "Company name printed on invoices"),
    (S_COMPANY_ADDRESS, "", "Company postal address on invoices"),
    (S_COMPANY_EMAIL, "", "Billing contact email"),
    (S_COMPANY_PHONE, "", "Billing contact phone"),
    (S_COMPANY_TAX_ID, "", "Company tax / VAT number"),
    (S_COMPANY_LOGO, "", "Absolute path to a logo image used on invoices"),
    (S_DEFAULT_CURRENCY, env.default_currency, "Default currency code (e.g. USD)"),
    (S_DEFAULT_TAX_RATE, str(env.default_tax_rate), "Default tax rate as a fraction (0.19 = 19%)"),
    (S_INVOICE_PREFIX, "INV", "Invoice number prefix"),
    (S_INVOICE_NEXT_NUMBER, "1", "Next invoice sequence number"),
    (S_GRACE_DAYS, str(env.grace_days), "Days after due date before auto-suspension"),
    (S_TRIAL_DAYS, str(env.trial_days), "Default trial length in days"),
    (S_LATE_FEE_PERCENT, "0", "Late fee percentage applied to overdue invoices"),
    (S_REMINDER_DAYS_BEFORE, "7", "Send a reminder N days before expiry"),
    (S_REMINDER_DAYS_AFTER, "3", "Send an overdue reminder N days after the due date"),
    (S_BANK_DETAILS, "", "Bank details shown on invoices"),
    (S_PAYMENT_METHODS, "bank_transfer,cash,cheque,online,other", "Accepted payment methods (comma separated)"),
    (S_DUNNING_ENABLED, "true", "Enable automated dunning reminders"),
    (S_AUTO_SUSPEND, "true", "Automatically suspend tenants past the grace period"),
    (S_AUTO_REACTIVATE, "true", "Automatically reactivate tenants when paid"),
    # --- Outgoing email (invoice sending + dunning reminders) -------------
    ("email_enabled", "true" if env.email_enabled else "false", "Send invoices and reminders by email"),
    ("smtp_host", env.smtp_host, "SMTP server host"),
    ("smtp_port", str(env.smtp_port), "SMTP server port"),
    ("smtp_user", env.smtp_user, "SMTP username"),
    ("smtp_password", "", "SMTP password (stored encrypted; leave empty to keep)"),
    ("smtp_use_tls", "true" if env.smtp_use_tls else "false", "Use STARTTLS (typically port 587)"),
    ("smtp_use_ssl", "true" if env.smtp_use_ssl else "false", "Use implicit TLS/SSL (typically port 465)"),
    ("email_from", env.email_from, "From address on outgoing email"),
    ("email_from_name", env.email_from_name, "From name on outgoing email"),
    ("email_timeout", str(env.email_timeout), "SMTP socket timeout in seconds"),
]


def seed_defaults(session: Session) -> None:
    """Insert any missing default setting rows."""
    existing = {s.key for s in session.scalars(select(Setting)).all()}
    for key, value, description in DEFAULTS:
        if key not in existing:
            session.add(Setting(key=key, value=value, description=description))
    session.flush()


def get_value(session: Session, key: str, default: str = "") -> str:
    """Return a raw setting value."""
    row = session.scalar(select(Setting).where(Setting.key == key))
    return row.value if row else default


def set_value(session: Session, key: str, value: str) -> None:
    """Upsert a setting value."""
    row = session.scalar(select(Setting).where(Setting.key == key))
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))
    session.flush()


def get_int(session: Session, key: str, default: int = 0) -> int:
    try:
        return int(get_value(session, key, str(default)) or default)
    except (TypeError, ValueError):
        return default


def get_decimal(session: Session, key: str, default: Decimal | str = "0") -> Decimal:
    try:
        return Decimal(get_value(session, key, str(default)) or str(default))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(str(default))


def get_bool(session: Session, key: str, default: bool = False) -> bool:
    return get_value(session, key, "true" if default else "false").strip().lower() in ("1", "true", "yes", "on")


def next_invoice_number(session: Session) -> str:
    """Consume and increment the invoice sequence, returning the new number."""
    prefix = get_value(session, S_INVOICE_PREFIX, "INV")
    current = get_int(session, S_INVOICE_NEXT_NUMBER, 1)
    set_value(session, S_INVOICE_NEXT_NUMBER, str(current + 1))
    return f"{prefix}-{current:06d}"


def company_block(session: Session) -> dict[str, str]:
    """Return the company details printed on invoices.

    Single source of truth shared by the invoice PDF renderer, the invoice email
    sender and the finance screens.
    """
    return {
        "name": get_value(session, S_COMPANY_NAME, "My SaaS Company"),
        "address": get_value(session, S_COMPANY_ADDRESS, ""),
        "email": get_value(session, S_COMPANY_EMAIL, ""),
        "phone": get_value(session, S_COMPANY_PHONE, ""),
        "tax_id": get_value(session, S_COMPANY_TAX_ID, ""),
        "bank_details": get_value(session, S_BANK_DETAILS, ""),
        "logo": get_value(session, S_COMPANY_LOGO, ""),
    }


def payment_methods(session: Session) -> list[str]:
    """Return the configured payment methods as a list."""
    raw = get_value(session, S_PAYMENT_METHODS, "bank_transfer,cash,cheque,online,other")
    return [method.strip() for method in raw.split(",") if method.strip()]
