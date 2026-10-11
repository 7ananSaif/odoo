"""Plans ("bouquets"): the set of apps + limits + pricing offered to tenants."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import PkMixin, TimestampMixin


class Plan(Base, PkMixin, TimestampMixin):
    """A commercial plan. Its allowed modules drive what a tenant may install."""

    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Default limits copied onto a new tenant (overridable per tenant).
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_warehouses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_companies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_storage_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=5120)
    # Whether portal/public users count against max_users on tenants of this plan.
    count_portal_users: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Pricing.
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    price_month: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    price_year: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    setup_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    price_extra_user: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    price_extra_warehouse: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)

    # Odoo apps allowed by this plan.
    modules: Mapped[list[PlanModule]] = relationship(
        "PlanModule", back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def module_names(self) -> list[str]:
        """Technical names of the allowed modules, base first."""
        names = [m.technical_name for m in self.modules if m.technical_name]
        names.sort()
        return names

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Plan {self.code}>"


class PlanModule(Base, PkMixin, TimestampMixin):
    """A single Odoo module allowed by a plan."""

    __tablename__ = "plan_modules"
    __table_args__ = (UniqueConstraint("plan_id", "technical_name", name="uq_plan_module"),)

    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True, nullable=False)
    technical_name: Mapped[str] = mapped_column(String(128), nullable=False)

    plan: Mapped[Plan] = relationship("Plan", back_populates="modules")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<PlanModule {self.technical_name}>"
