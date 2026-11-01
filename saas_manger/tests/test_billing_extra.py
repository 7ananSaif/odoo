"""Debit notes, deposits, refunds, churn and expiring subscriptions."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.models.billing import Payment
from app.models.enums import CreditNoteKind, PaymentKind
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.services import billing_service


def make_tenant(session, **kwargs) -> Tenant:
    tenant = Tenant(
        name=kwargs.get("name", "Acme Inc"),
        subdomain=kwargs.get("subdomain", "acme"),
        db_name=kwargs.get("db_name", "acme"),
        status=kwargs.get("status", "active"),
        expiry_date=kwargs.get("expiry_date"),
    )
    session.add(tenant)
    session.flush()
    return tenant


def make_plan(session, **kwargs) -> Plan:
    plan = Plan(
        name=kwargs.get("name", "Standard"),
        code=kwargs.get("code", "standard"),
        price_month=kwargs.get("price_month", Decimal("100")),
        price_year=kwargs.get("price_year", Decimal("1000")),
        tax_rate=kwargs.get("tax_rate", Decimal("0")),
        currency=kwargs.get("currency", "USD"),
    )
    session.add(plan)
    session.flush()
    return plan


def sent_invoice(session, tenant, plan):
    invoice = billing_service.generate_invoice(
        session, tenant, plan=plan, include_setup_fee=False,
    )
    billing_service.mark_sent(session, invoice)
    return invoice


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
def test_debit_note_increases_balance(session):
    tenant = make_tenant(session)
    plan = make_plan(session)
    invoice = sent_invoice(session, tenant, plan)
    assert billing_service.tenant_balance(session, tenant.id) == Decimal("100.00")

    note = billing_service.create_debit_note(
        session, tenant=tenant, invoice=invoice, amount=Decimal("40"), reason="extra work",
    )
    assert note.kind == CreditNoteKind.DEBIT.value
    assert note.amount == Decimal("40.00")
    assert note.number.startswith("DN-")
    assert note.is_debit is True
    assert billing_service.tenant_balance(session, tenant.id) == Decimal("140.00")


def test_credit_note_stays_negative_and_reduces(session):
    tenant = make_tenant(session)
    plan = make_plan(session)
    sent_invoice(session, tenant, plan)
    note = billing_service.create_credit_note(
        session, tenant=tenant, invoice=None, amount=Decimal("25"), reason="goodwill",
    )
    assert note.kind == CreditNoteKind.CREDIT.value
    assert note.amount == Decimal("-25.00")
    assert note.is_debit is False
    assert note.number.startswith("CN-")
    assert billing_service.tenant_balance(session, tenant.id) == Decimal("75.00")


def test_note_amounts_must_be_positive(session):
    tenant = make_tenant(session)
    for kind in (CreditNoteKind.CREDIT.value, CreditNoteKind.DEBIT.value):
        try:
            billing_service.create_note(
                session, tenant=tenant, invoice=None, amount=Decimal("0"), kind=kind,
            )
        except billing_service.BillingError:
            pass
        else:  # pragma: no cover - must not happen
            raise AssertionError("zero-amount notes must be rejected")


# ---------------------------------------------------------------------------
# Deposits / refunds
# ---------------------------------------------------------------------------
def test_deposit_reduces_balance_without_allocating(session):
    tenant = make_tenant(session)
    plan = make_plan(session)
    invoice = sent_invoice(session, tenant, plan)

    deposit = billing_service.record_deposit(
        session, tenant=tenant, amount=Decimal("30"), reference="advance",
    )
    assert isinstance(deposit, Payment)
    assert deposit.kind == PaymentKind.DEPOSIT.value
    assert deposit.amount == Decimal("30.00")
    # The invoice itself is untouched: a deposit is not allocation.
    assert invoice.amount_paid == Decimal("0.00")
    assert invoice.balance == Decimal("100.00")
    # But the tenant's net position improves.
    assert billing_service.tenant_balance(session, tenant.id) == Decimal("70.00")


def test_refund_increases_balance_and_is_negative(session):
    tenant = make_tenant(session)
    plan = make_plan(session)
    sent_invoice(session, tenant, plan)

    refund = billing_service.record_refund(
        session, tenant=tenant, amount=Decimal("20"), reference="overcharge",
    )
    assert refund.kind == PaymentKind.REFUND.value
    assert refund.amount == Decimal("-20.00")
    assert refund.is_outgoing is True
    assert billing_service.tenant_balance(session, tenant.id) == Decimal("120.00")


def test_payment_kind_must_be_known(session):
    tenant = make_tenant(session)
    try:
        billing_service.record_payment(session, tenant=tenant, amount=Decimal("10"), kind="bogus")
    except billing_service.BillingError:
        pass
    else:  # pragma: no cover - must not happen
        raise AssertionError("unknown payment kinds must be rejected")


# ---------------------------------------------------------------------------
# Churn / expiry reports
# ---------------------------------------------------------------------------
def test_expiring_subscriptions_window(session):
    today = date.today()
    soon = make_tenant(session, name="Soon", subdomain="soon", db_name="soon",
                       expiry_date=today + timedelta(days=5))
    make_tenant(session, name="Later", subdomain="later", db_name="later",
                expiry_date=today + timedelta(days=90))

    expiring = billing_service.expiring_subscriptions(session, within_days=30, today=today)
    assert soon in expiring
    assert all(t.subdomain != "later" for t in expiring)


def test_expired_subscriptions_excludes_active(session):
    today = date.today()
    churned = make_tenant(session, name="Old", subdomain="old", db_name="old",
                          status="cancelled", expiry_date=today - timedelta(days=10))
    make_tenant(session, name="Live", subdomain="live", db_name="live",
                status="active", expiry_date=today - timedelta(days=10))

    expired = billing_service.expired_subscriptions(session, today=today)
    assert churned in expired
    assert all(t.subdomain != "live" for t in expired)


def test_churn_stats_counts_and_rate(session):
    today = date.today()
    make_tenant(session, name="A", subdomain="a", db_name="a", status="active")
    make_tenant(session, name="B", subdomain="b", db_name="b", status="trial")
    make_tenant(session, name="C", subdomain="c", db_name="c", status="cancelled",
                expiry_date=today - timedelta(days=5))
    make_tenant(session, name="D", subdomain="d", db_name="d", status="expired",
                expiry_date=today - timedelta(days=40))

    stats = billing_service.churn_stats(session, months=12, today=today)
    assert stats["active"] == 2
    assert stats["churned"] == 2
    # 2 churned out of 4 (active + churned)
    assert stats["churn_rate"] == 50.0
