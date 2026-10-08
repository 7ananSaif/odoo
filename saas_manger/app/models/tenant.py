"""A tenant = one Odoo database + one subdomain + one plan/subscription."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import PkMixin, TimestampMixin


class Tenant(Base, PkMixin, TimestampMixin):
    """A client database managed by the manager."""

    __tablename__ = "tenants"

    # --- Identity ----------------------------------------------------------
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subdomain: Mapped[str] = mapped_column(String(63), unique=True, index=True, nullable=False)
    db_name: Mapped[str] = mapped_column(String(63), unique=True, index=True, nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    country: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    tax_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # --- Plan / lifecycle --------------------------------------------------
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id", ondelete="SET NULL"), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="trial", index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Limits (copied from the plan, overridable per tenant) -------------
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_warehouses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_companies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_storage_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=5120)
    max_db_size_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0 = unlimited
    # Whether portal/public users also consume the max_users quota (per-tenant).
    count_portal_users: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # '1' → a suspended/expired tenant is forced read-only; '0' → only the page.
    block_writes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Whether the plan limits are enforced at all inside the client DB.
    enforce_limits: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- Usage (refreshed by a cron/worker) --------------------------------
    current_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_warehouses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_companies: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_storage_mb: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    current_db_size_mb: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_backup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_usage_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Provisioning metadata ---------------------------------------------
    admin_login: Mapped[str] = mapped_column(String(255), nullable=False, default="admin")
    # Admin password of the client DB, encrypted at rest (Fernet). Required to
    # (re)authenticate the manager against the client's RPC/JSON-2 endpoint.
    admin_password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional per-tenant API key (encrypted) for JSON-2 calls.
    api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    provisioned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    plan: Mapped["Plan | None"] = relationship("Plan", lazy="joined")  # noqa: F821

    @property
    def is_blocked(self) -> bool:
        """Whether the tenant must be read-only (suspended/expired/cancelled)."""
        return self.status in ("suspended", "expired", "cancelled") or self.maintenance_mode

    @property
    def url(self) -> str:
        from app.config import settings  # noqa: PLC0415

        return settings.tenant_url(self.subdomain)

    def usage_percent(self, key: str) -> int:
        """Return usage as a percentage of the matching limit (0 = unlimited)."""
        current = {
            "users": self.current_users,
            "warehouses": self.current_warehouses,
            "companies": self.current_companies,
            "storage": float(self.current_storage_mb),
            "db_size": float(self.current_db_size_mb),
        }[key]
        limit = {
            "users": self.max_users,
            "warehouses": self.max_warehouses,
            "companies": self.max_companies,
            "storage": self.max_storage_mb,
            "db_size": self.max_db_size_mb,
        }[key]
        if not limit:
            return 0
        return int(round(current * 100 / limit))

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Tenant {self.subdomain} ({self.db_name})>"
