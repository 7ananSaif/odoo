"""Key/value store for general and financial settings."""
from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PkMixin, TimestampMixin

# Well-known setting keys (kept here so code and templates never hard-code strings).
S_DEFAULT_CURRENCY = "default_currency"
S_DEFAULT_TAX_RATE = "default_tax_rate"
S_INVOICE_PREFIX = "invoice_prefix"
S_INVOICE_NEXT_NUMBER = "invoice_next_number"
S_COMPANY_NAME = "company_name"
S_COMPANY_ADDRESS = "company_address"
S_COMPANY_EMAIL = "company_email"
S_COMPANY_PHONE = "company_phone"
S_COMPANY_TAX_ID = "company_tax_id"
S_COMPANY_LOGO = "company_logo"  # path or data URI
S_GRACE_DAYS = "grace_days"
S_TRIAL_DAYS = "trial_days"
S_LATE_FEE_PERCENT = "late_fee_percent"
S_REMINDER_DAYS_BEFORE = "reminder_days_before"
S_REMINDER_DAYS_AFTER = "reminder_days_after"
S_BANK_DETAILS = "bank_details"
S_PAYMENT_METHODS = "payment_methods"
S_DUNNING_ENABLED = "dunning_enabled"
S_AUTO_SUSPEND = "auto_suspend"
S_AUTO_REACTIVATE = "auto_reactivate"


class Setting(Base, PkMixin, TimestampMixin):
    """A single configuration value, editable from the Settings page."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Setting {self.key}>"
