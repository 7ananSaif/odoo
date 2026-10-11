"""Billing: subscriptions, invoice generation, payments, balances and revenue metrics."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.billing import CreditNote, Invoice, InvoiceLine, Payment, Subscription
from app.models.enums import (
    BillingCycle,
    CreditNoteKind,
    InvoiceStatus,
    PaymentKind,
    PaymentMethod,
    SubscriptionStatus,
    TenantStatus,
)
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.services import audit, settings_service

_logger = logging.getLogger(__name__)

CENT = Decimal("0.01")


class BillingError(RuntimeError):
    """Raised for invalid billing operations."""


def money(value: Decimal | float | int | str) -> Decimal:
    """Quantise a value to two decimals (banker-safe half-up)."""
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------
def create_subscription(
    session: Session,
    tenant: Tenant,
    plan: Plan | None,
    *,
    cycle: str = BillingCycle.MONTHLY.value,
    start: date | None = None,
    tax_rate: Decimal | None = None,
    payment_terms_days: int = 15,
) -> Subscription:
    """Create the recurring subscription for a tenant."""
    start = start or date.today()
    subscription = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id if plan else None,
        cycle=cycle,
        status=SubscriptionStatus.TRIAL.value if tenant.status == TenantStatus.TRIAL.value else SubscriptionStatus.ACTIVE.value,
        start_date=start,
        next_invoice_date=_advance(start, cycle),
        currency=(plan.currency if plan else settings_service.get_value(session, "default_currency", "USD")),
        tax_rate=tax_rate if tax_rate is not None else (plan.tax_rate if plan else Decimal("0")),
        payment_terms_days=payment_terms_days,
    )
    session.add(subscription)
    session.flush()
    return subscription


def _advance(start: date, cycle: str) -> date:
    """Return the next billing date one cycle after ``start``."""
    if cycle == BillingCycle.YEARLY.value:
        return start.replace(year=start.year + 1)
    # monthly: add one month, clamping the day
    year = start.year + (1 if start.month == 12 else 0)
    month = 1 if start.month == 12 else start.month + 1
    day = min(start.day, _days_in_month(year, month))
    return start.replace(year=year, month=month, day=day)


def _days_in_month(year: int, month: int) -> int:
    import calendar  # noqa: PLC0415

    return calendar.monthrange(year, month)[1]


# ---------------------------------------------------------------------------
# Invoice generation
# ---------------------------------------------------------------------------
@dataclass
class InvoiceDraft:
    """Computed invoice amounts before persistence."""

    lines: list[InvoiceLine] = field(default_factory=list)
    subtotal: Decimal = Decimal("0")
    discount_total: Decimal = Decimal("0")
    tax_total: Decimal = Decimal("0")
    total: Decimal = Decimal("0")


def compute_invoice_lines(
    session: Session,
    tenant: Tenant,
    plan: Plan | None,
    subscription: Subscription | None,
    *,
    period_start: date,
    period_end: date,
    include_setup_fee: bool = False,
) -> InvoiceDraft:
    """Compute the invoice lines for one billing period.

    Includes: the plan price, the setup fee (first invoice), the charge for extra
    users/warehouses beyond the plan, then discount and tax.
    """
    draft = InvoiceDraft()
    if plan is None:
        return draft

    yearly = subscription and subscription.cycle == BillingCycle.YEARLY.value
    base_price = plan.price_year if yearly else plan.price_month
    period_label = f"{period_start:%Y-%m-%d} → {period_end:%Y-%m-%d}"

    draft.lines.append(InvoiceLine(
        description=f"{plan.name} ({'yearly' if yearly else 'monthly'}) {period_label}",
        quantity=Decimal("1"),
        unit_price=money(base_price),
        tax_rate=plan.tax_rate,
        line_total=money(base_price),
    ))

    if include_setup_fee and plan.setup_fee:
        draft.lines.append(InvoiceLine(
            description="Setup fee",
            quantity=Decimal("1"),
            unit_price=money(plan.setup_fee),
            tax_rate=plan.tax_rate,
            line_total=money(plan.setup_fee),
        ))

    extra_users = max(0, tenant.current_users - plan.max_users)
    if extra_users and plan.price_extra_user:
        line_total = money(plan.price_extra_user * extra_users)
        draft.lines.append(InvoiceLine(
            description=f"Extra users ({extra_users})",
            quantity=Decimal(extra_users),
            unit_price=money(plan.price_extra_user),
            tax_rate=plan.tax_rate,
            line_total=line_total,
        ))

    extra_wh = max(0, tenant.current_warehouses - plan.max_warehouses)
    if extra_wh and plan.price_extra_warehouse:
        line_total = money(plan.price_extra_warehouse * extra_wh)
        draft.lines.append(InvoiceLine(
            description=f"Extra warehouses ({extra_wh})",
            quantity=Decimal(extra_wh),
            unit_price=money(plan.price_extra_warehouse),
            tax_rate=plan.tax_rate,
            line_total=line_total,
        ))

    draft.subtotal = money(sum((line.line_total for line in draft.lines), Decimal("0")))

    # Discount (fixed then percent).
    discount = Decimal("0")
    if subscription:
        if subscription.discount_fixed:
            discount += money(subscription.discount_fixed)
        if subscription.discount_percent:
            discount += money(draft.subtotal * subscription.discount_percent / Decimal("100"))
    draft.discount_total = min(discount, draft.subtotal)

    tax_rate = (subscription.tax_rate if subscription and subscription.tax_rate else plan.tax_rate) or Decimal("0")
    taxable = draft.subtotal - draft.discount_total
    draft.tax_total = money(taxable * tax_rate)
    draft.total = money(taxable + draft.tax_total)
    return draft


def generate_invoice(
    session: Session,
    tenant: Tenant,
    *,
    subscription: Subscription | None = None,
    plan: Plan | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    include_setup_fee: bool | None = None,
    actor: str = "system",
) -> Invoice:
    """Create a draft invoice for a tenant's current billing period."""
    plan = plan or (tenant.plan if tenant.plan else None)
    subscription = subscription or session.scalar(
        select(Subscription).where(Subscription.tenant_id == tenant.id).order_by(Subscription.id.desc())
    )
    today = date.today()
    period_start = period_start or (subscription.next_invoice_date if subscription and subscription.next_invoice_date else today)
    cycle = subscription.cycle if subscription else BillingCycle.MONTHLY.value
    period_end = period_end or _advance(period_start, cycle)

    if include_setup_fee is None:
        prior_count = session.scalar(
            select(func.count(Invoice.id)).where(Invoice.tenant_id == tenant.id)
        ) or 0
        include_setup_fee = prior_count == 0

    draft = compute_invoice_lines(
        session, tenant, plan, subscription,
        period_start=period_start, period_end=period_end, include_setup_fee=include_setup_fee,
    )
    terms = subscription.payment_terms_days if subscription else settings_service.get_int(session, "grace_days", 15)
    invoice = Invoice(
        number=settings_service.next_invoice_number(session),
        tenant_id=tenant.id,
        subscription_id=subscription.id if subscription else None,
        status=InvoiceStatus.DRAFT.value,
        issue_date=today,
        due_date=today + timedelta(days=terms or 15),
        period_start=period_start,
        period_end=period_end,
        currency=(plan.currency if plan else "USD"),
        subtotal=draft.subtotal,
        discount_total=draft.discount_total,
        tax_total=draft.tax_total,
        total=draft.total,
    )
    session.add(invoice)
    session.flush()
    for line in draft.lines:
        line.invoice_id = invoice.id
        session.add(line)
    session.flush()

    if subscription:
        subscription.next_invoice_date = period_end
    audit.record(session, action="invoice.create", actor=actor, target_type="invoice",
                 target_id=invoice.id, detail=f"{invoice.number} total={invoice.total} {invoice.currency}")
    return invoice


def mark_sent(session: Session, invoice: Invoice, *, actor: str = "system") -> None:
    if invoice.status == InvoiceStatus.CANCELLED.value:
        raise BillingError("Cannot send a cancelled invoice")
    invoice.status = InvoiceStatus.SENT.value
    invoice.sent_at = datetime.now(timezone.utc)
    audit.record(session, action="invoice.send", actor=actor, target_type="invoice",
                 target_id=invoice.id, detail=invoice.number)
    session.flush()


def cancel_invoice(session: Session, invoice: Invoice, *, actor: str = "system") -> None:
    """Invoices cannot be deleted after being sent — cancel them instead."""
    invoice.status = InvoiceStatus.CANCELLED.value
    audit.record(session, action="invoice.cancel", actor=actor, target_type="invoice",
                 target_id=invoice.id, detail=invoice.number)
    session.flush()


def delete_invoice(session: Session, invoice: Invoice) -> None:
    """Delete a DRAFT invoice only. Sent invoices must be cancelled via a credit note."""
    if invoice.status != InvoiceStatus.DRAFT.value:
        raise BillingError("Only draft invoices can be deleted; cancel with a credit note instead")
    session.delete(invoice)
    session.flush()


# ---------------------------------------------------------------------------
# Payments / balances
# ---------------------------------------------------------------------------
def record_payment(
    session: Session,
    *,
    tenant: Tenant,
    amount: Decimal,
    method: str = PaymentMethod.BANK_TRANSFER.value,
    reference: str = "",
    invoice: Invoice | None = None,
    on_date: date | None = None,
    notes: str = "",
    kind: str = PaymentKind.PAYMENT.value,
    actor: str = "system",
) -> Payment:
    """Record a money movement and allocate it to an invoice when it settles one.

    ``kind`` is one of :class:`~app.models.enums.PaymentKind`:

    * ``payment`` — settles an invoice (allocated to it, or to the oldest
      outstanding one when no invoice is given);
    * ``deposit`` — money received in advance, never allocated to an invoice;
    * ``refund``  — money paid back to the tenant; stored as a negative amount
      and **never** allocated, so it raises the outstanding balance instead.
    """
    amount = money(abs(amount))
    if amount <= 0:
        raise BillingError("Amount must be positive")
    if kind not in tuple(k.value for k in PaymentKind):
        raise BillingError(f"Unknown payment kind: {kind}")

    is_refund = kind == PaymentKind.REFUND.value
    signed_amount = -amount if is_refund else amount
    payment = Payment(
        tenant_id=tenant.id,
        invoice_id=invoice.id if invoice and not is_refund else None,
        date=on_date or date.today(),
        amount=signed_amount,
        currency=invoice.currency if invoice else settings_service.get_value(session, "default_currency", "USD"),
        method=method,
        kind=kind,
        reference=reference,
        notes=notes,
    )
    session.add(payment)
    session.flush()

    # Only money coming in is allocated. Deposits stay unallocated by design.
    if not is_refund and kind != PaymentKind.DEPOSIT.value:
        target = invoice or _oldest_outstanding(session, tenant.id)
        if target is not None:
            target.amount_paid = money(target.amount_paid + amount)
            if target.balance <= 0:
                target.status = InvoiceStatus.PAID.value
                target.paid_at = datetime.now(timezone.utc)

    audit.record(session, action=f"{kind}.record", actor=actor, target_type="tenant",
                 target_id=tenant.id,
                 detail=f"{signed_amount} {payment.currency} via {method}")
    session.flush()
    return payment


def record_deposit(
    session: Session, *, tenant: Tenant, amount: Decimal, method: str = PaymentMethod.BANK_TRANSFER.value,
    reference: str = "", on_date: date | None = None, notes: str = "", actor: str = "system",
) -> Payment:
    """Record a deposit (money received in advance, not tied to an invoice)."""
    return record_payment(session, tenant=tenant, amount=amount, method=method, reference=reference,
                          on_date=on_date, notes=notes, kind=PaymentKind.DEPOSIT.value, actor=actor)


def record_refund(
    session: Session, *, tenant: Tenant, amount: Decimal, method: str = PaymentMethod.BANK_TRANSFER.value,
    reference: str = "", on_date: date | None = None, notes: str = "", actor: str = "system",
) -> Payment:
    """Record a refund paid back to the tenant (increases what they owe)."""
    return record_payment(session, tenant=tenant, amount=amount, method=method, reference=reference,
                          on_date=on_date, notes=notes, kind=PaymentKind.REFUND.value, actor=actor)


def _oldest_outstanding(session: Session, tenant_id: int) -> Invoice | None:
    return session.scalar(
        select(Invoice)
        .where(Invoice.tenant_id == tenant_id, Invoice.status.in_([InvoiceStatus.SENT.value, InvoiceStatus.OVERDUE.value]))
        .order_by(Invoice.due_date)
    )


def create_credit_note(
    session: Session, *, tenant: Tenant, invoice: Invoice | None, amount: Decimal,
    reason: str = "", on_date: date | None = None, actor: str = "system",
) -> CreditNote:
    """Issue a credit note (reduces the balance) against a tenant / invoice."""
    return create_note(session, tenant=tenant, invoice=invoice, amount=amount, reason=reason,
                       on_date=on_date, kind=CreditNoteKind.CREDIT.value, actor=actor)


def create_note(
    session: Session, *, tenant: Tenant, invoice: Invoice | None, amount: Decimal,
    reason: str = "", on_date: date | None = None,
    kind: str = CreditNoteKind.CREDIT.value, actor: str = "system",
) -> CreditNote:
    """Issue a credit note (reduces the balance) or a debit note (raises it).

    The signed ``amount`` is the source of truth: credits are stored negative and
    debit notes positive, so the balance is always ``due - paid + notes``.
    """
    if kind not in tuple(k.value for k in CreditNoteKind):
        raise BillingError(f"Unknown note kind: {kind}")
    magnitude = money(abs(amount))
    if magnitude <= 0:
        raise BillingError("Note amount must be positive")
    is_debit = kind == CreditNoteKind.DEBIT.value
    sequence_key = "debit_next_number" if is_debit else "credit_next_number"
    seq = settings_service.get_int(session, sequence_key, 1)
    settings_service.set_value(session, sequence_key, str(seq + 1))
    note = CreditNote(
        number=f"{'DN' if is_debit else 'CN'}-{seq:06d}",
        tenant_id=tenant.id,
        invoice_id=invoice.id if invoice else None,
        issue_date=on_date or date.today(),
        amount=magnitude if is_debit else -magnitude,
        kind=kind,
        currency=invoice.currency if invoice else settings_service.get_value(session, "default_currency", "USD"),
        reason=reason,
    )
    session.add(note)
    audit.record(session, action=f"{kind}_note.create", actor=actor, target_type="tenant",
                 target_id=tenant.id, detail=f"{note.number} {note.amount}")
    session.flush()
    return note


def create_debit_note(
    session: Session, *, tenant: Tenant, invoice: Invoice | None = None, amount: Decimal = Decimal("0"),
    reason: str = "", on_date: date | None = None, actor: str = "system",
) -> CreditNote:
    """Issue a debit note (increases what the tenant owes)."""
    return create_note(session, tenant=tenant, invoice=invoice, amount=amount, reason=reason,
                       on_date=on_date, kind=CreditNoteKind.DEBIT.value, actor=actor)


def tenant_balance(session: Session, tenant_id: int) -> Decimal:
    """Return the tenant's outstanding balance (invoices − payments − credits)."""
    invoices = session.scalars(
        select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.status != InvoiceStatus.CANCELLED.value)
    ).all()
    due = sum((money(inv.total + inv.late_fee) for inv in invoices), Decimal("0"))
    paid = session.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.tenant_id == tenant_id)
    ) or 0
    credits = session.scalar(
        select(func.coalesce(func.sum(CreditNote.amount), 0)).where(CreditNote.tenant_id == tenant_id)
    ) or 0
    # Credit notes are stored as negative amounts, so they are ADDED to the balance.
    return money(Decimal(str(due)) - Decimal(str(paid)) + Decimal(str(credits)))


# ---------------------------------------------------------------------------
# Late fees, overdue sweep, dunning
# ---------------------------------------------------------------------------
def mark_overdue(session: Session, *, today: date | None = None, actor: str = "system") -> list[Invoice]:
    """Mark sent invoices past their due date as overdue and apply late fees."""
    today = today or date.today()
    late_fee_percent = settings_service.get_decimal(session, "late_fee_percent", "0")
    changed: list[Invoice] = []
    sent = session.scalars(select(Invoice).where(Invoice.status == InvoiceStatus.SENT.value)).all()
    for invoice in sent:
        if invoice.due_date < today:
            invoice.status = InvoiceStatus.OVERDUE.value
            if late_fee_percent and invoice.late_fee == 0:
                invoice.late_fee = money((invoice.total - invoice.discount_total) * late_fee_percent / Decimal("100"))
            changed.append(invoice)
            audit.record(session, action="invoice.overdue", actor=actor, target_type="invoice",
                         target_id=invoice.id, level="warning", detail=invoice.number)
    session.flush()
    return changed


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def mrr(session: Session, *, today: date | None = None) -> Decimal:
    """Monthly recurring revenue: active subscriptions normalised to one month."""
    today = today or date.today()
    total = Decimal("0")
    subs = session.scalars(
        select(Subscription).where(Subscription.status.in_([SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIAL.value]))
    ).all()
    for sub in subs:
        plan = session.get(Plan, sub.plan_id) if sub.plan_id else None
        if not plan:
            continue
        monthly = plan.price_year / Decimal("12") if sub.cycle == BillingCycle.YEARLY.value else plan.price_month
        discount = Decimal("1") - (sub.discount_percent or Decimal("0")) / Decimal("100")
        total += money(monthly * discount)
    return money(total)


def yearly_revenue(session: Session, year: int) -> Decimal:
    """Total invoiced revenue (paid + sent + overdue) for a calendar year."""
    total = session.scalar(
        select(func.coalesce(func.sum(Invoice.total), 0))
        .where(func.extract("year", Invoice.issue_date) == year)
        .where(Invoice.status != InvoiceStatus.CANCELLED.value)
    ) or 0
    return money(Decimal(str(total)))


def outstanding_total(session: Session) -> Decimal:
    """Sum of all unpaid balances across tenants."""
    invoices = session.scalars(
        select(Invoice).where(Invoice.status.in_([InvoiceStatus.SENT.value, InvoiceStatus.OVERDUE.value]))
    ).all()
    return money(sum((inv.balance for inv in invoices), Decimal("0")))


def overdue_total(session: Session) -> Decimal:
    invoices = session.scalars(select(Invoice).where(Invoice.status == InvoiceStatus.OVERDUE.value)).all()
    return money(sum((inv.balance for inv in invoices), Decimal("0")))


def revenue_per_plan(session: Session) -> list[dict]:
    """Return [{plan, currency, total}] of invoiced amounts grouped by plan."""
    rows: dict[str, Decimal] = {}
    currency_by_plan: dict[str, str] = {}
    for invoice in session.scalars(select(Invoice).where(Invoice.status != InvoiceStatus.CANCELLED.value)).all():
        tenant = session.get(Tenant, invoice.tenant_id)
        plan = session.get(Plan, tenant.plan_id) if tenant and tenant.plan_id else None
        name = plan.name if plan else "—"
        rows[name] = rows.get(name, Decimal("0")) + money(invoice.total)
        currency_by_plan[name] = invoice.currency
    return [
        {"plan": name, "currency": currency_by_plan.get(name, "USD"), "total": money(total)}
        for name, total in sorted(rows.items())
    ]


def expiring_subscriptions(session: Session, *, within_days: int = 30, today: date | None = None) -> list[Tenant]:
    """Tenants whose subscription expires within ``within_days`` (active/trial)."""
    from datetime import timedelta  # noqa: PLC0415

    today = today or date.today()
    horizon = today + timedelta(days=within_days)
    return list(session.scalars(
        select(Tenant)
        .where(Tenant.expiry_date.is_not(None))
        .where(Tenant.expiry_date >= today)
        .where(Tenant.expiry_date <= horizon)
        .where(Tenant.status.in_([TenantStatus.TRIAL.value, TenantStatus.ACTIVE.value]))
        .order_by(Tenant.expiry_date)
    ).all())


def expired_subscriptions(session: Session, *, today: date | None = None) -> list[Tenant]:
    """Tenants whose expiry date has passed and are no longer active/trial."""
    today = today or date.today()
    return list(session.scalars(
        select(Tenant)
        .where(Tenant.expiry_date.is_not(None))
        .where(Tenant.expiry_date < today)
        .where(Tenant.status.notin_([TenantStatus.TRIAL.value, TenantStatus.ACTIVE.value]))
        .order_by(Tenant.expiry_date)
    ).all())


def churn_stats(session: Session, *, months: int = 12, today: date | None = None) -> dict:
    """Return a simple churn picture over the last ``months`` months.

    "Churned" = tenants that ended up cancelled/expired within the window (their
    expiry date falls inside it). ``churn_rate`` is churned / (active + churned),
    expressed as a percentage.
    """
    from datetime import timedelta  # noqa: PLC0415

    today = today or date.today()
    start = today - timedelta(days=30 * months)
    tenants = list(session.scalars(select(Tenant)).all())

    active = [t for t in tenants if t.status in (TenantStatus.TRIAL.value, TenantStatus.ACTIVE.value)]
    churned = [
        t for t in tenants
        if t.status in (TenantStatus.CANCELLED.value, TenantStatus.EXPIRED.value)
        and t.expiry_date is not None
        and start <= t.expiry_date <= today
    ]
    base = len(active) + len(churned)
    rate = (len(churned) / base * 100) if base else 0.0
    return {
        "window_months": months,
        "active": len(active),
        "churned": len(churned),
        "churn_rate": round(rate, 2),
    }
