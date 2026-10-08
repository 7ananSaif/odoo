"""Financial models: subscriptions, invoices, invoice lines, payments, credit notes."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import PkMixin, TimestampMixin

ZERO = Decimal("0")


def decimal_or_zero(value: Decimal | float | int | str | None) -> Decimal:
    """Coerce any numeric-ish value to ``Decimal`` (0 when null/invalid)."""
    if value is None:
        return ZERO
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        return ZERO


class Subscription(Base, PkMixin, TimestampMixin):
    """The recurring billing agreement between a tenant and a plan."""

    __tablename__ = "subscriptions"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id", ondelete="SET NULL"), nullable=True)

    cycle: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="trial", index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    discount_fixed: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    invoices: Mapped[list[Invoice]] = relationship(
        "Invoice", back_populates="subscription", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Subscription tenant={self.tenant_id} {self.cycle}>"


class Invoice(Base, PkMixin, TimestampMixin):
    """A customer invoice. Cannot be deleted once sent — cancel via a credit note."""

    __tablename__ = "invoices"

    number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    late_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    subscription: Mapped[Subscription | None] = relationship("Subscription", back_populates="invoices")
    lines: Mapped[list[InvoiceLine]] = relationship(
        "InvoiceLine", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def balance(self) -> Decimal:
        """Remaining amount due."""
        return (self.total + self.late_fee) - self.amount_paid

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invoice {self.number} {self.status}>"


class InvoiceLine(Base, PkMixin, TimestampMixin):
    """A single billed item (plan price, extra users, setup fee, ...)."""

    __tablename__ = "invoice_lines"

    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="lines")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<InvoiceLine {self.description}>"


class Payment(Base, PkMixin, TimestampMixin):
    """A payment recorded against a tenant (optionally against an invoice)."""

    __tablename__ = "payments"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # Signed amount: positive = money received (payment/deposit),
    # negative = money paid back to the tenant (refund).
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="bank_transfer")
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="payment", index=True)
    reference: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    @property
    def is_outgoing(self) -> bool:
        """True for a refund (money leaving the provider)."""
        return decimal_or_zero(self.amount) < 0

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Payment {self.amount} {self.method} {self.kind}>"


class CreditNote(Base, PkMixin, TimestampMixin):
    """A credit/debit note used to adjust an invoice without deleting it."""

    __tablename__ = "credit_notes"

    number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Signed amount: negative = credit (reduces the balance),
    # positive = debit note (increases the balance).
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="credit", index=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    @property
    def is_debit(self) -> bool:
        """True for a debit note (increases what the tenant owes)."""
        return decimal_or_zero(self.amount) > 0

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CreditNote {self.number} {self.amount} {self.kind}>"
