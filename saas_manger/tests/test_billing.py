"""Invoice generation, payments, balances and revenue metrics."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.models.billing import Invoice, Payment
from app.models.enums import InvoiceStatus
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.services import billing_service
from app.services import settings_service


def make_tenant(session, **kwargs) -> Tenant:
    tenant = Tenant(
        name=kwargs.get("name", "Acme Inc"),
        subdomain=kwargs.get("subdomain", "acme"),
        db_name=kwargs.get("db_name", "acme"),
        status=kwargs.get("status", "active"),
        current_users=kwargs.get("current_users", 3),
        current_warehouses=kwargs.get("current_warehouses", 1),
        max_users=kwargs.get("max_users", 5),
        max_warehouses=kwargs.get("max_warehouses", 1),
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
        setup_fee=kwargs.get("setup_fee", Decimal("50")),
        price_extra_user=kwargs.get("price_extra_user", Decimal("10")),
        price_extra_warehouse=kwargs.get("price_extra_warehouse", Decimal("20")),
        tax_rate=kwargs.get("tax_rate", Decimal("0.19")),
        max_users=kwargs.get("max_users", 5),
        max_warehouses=kwargs.get("max_warehouses", 1),
        currency=kwargs.get("currency", "USD"),
    )
    session.add(plan)
    session.flush()
    return plan


def test_invoice_includes_setup_fee_plan_and_tax(session):
    tenant = make_tenant(session)
    plan = make_plan(session)
    subscription = billing_service.create_subscription(session, tenant, plan)
    invoice = billing_service.generate_invoice(session, tenant, subscription=subscription, plan=plan)

    descriptions = [line.description for line in invoice.lines]
    assert any("Setup fee" in d for d in descriptions)
    assert any("Standard (monthly)" in d for d in descriptions)
    # 100 plan + 50 setup = 150 subtotal, tax 19% = 28.50, total 178.50
    assert invoice.subtotal == Decimal("150.00")
    assert invoice.tax_total == Decimal("28.50")
    assert invoice.total == Decimal("178.50")


def test_extra_users_and_warehouses_are_billed(session):
    tenant = make_tenant(session, current_users=8, current_warehouses=3)
    plan = make_plan(session, max_users=5, max_warehouses=1)
    subscription = billing_service.create_subscription(session, tenant, plan)
    invoice = billing_service.generate_invoice(
        session, tenant, subscription=subscription, plan=plan, include_setup_fee=False,
    )
    descriptions = " ".join(line.description for line in invoice.lines)
    assert "Extra users (3)" in descriptions
    assert "Extra warehouses (2)" in descriptions
    # 100 + 3*10 + 2*20 = 170
    assert invoice.subtotal == Decimal("170.00")


def test_discount_and_tax_applied(session):
    tenant = make_tenant(session)
    plan = make_plan(session)
    subscription = billing_service.create_subscription(session, tenant, plan)
    subscription.discount_percent = Decimal("10")
    subscription.discount_fixed = Decimal("5")
    session.flush()
    invoice = billing_service.generate_invoice(
        session, tenant, subscription=subscription, plan=plan, include_setup_fee=False,
    )
    # subtotal 100, discount 15 -> taxable 85, tax 16.15, total 101.15
    assert invoice.discount_total == Decimal("15.00")
    assert invoice.tax_total == Decimal("16.15")
    assert invoice.total == Decimal("101.15")


def test_payment_updates_invoice_and_balance(session):
    tenant = make_tenant(session)
    plan = make_plan(session, tax_rate=Decimal("0"))
    subscription = billing_service.create_subscription(session, tenant, plan)
    invoice = billing_service.generate_invoice(
        session, tenant, subscription=subscription, plan=plan, include_setup_fee=False,
    )
    assert invoice.total == Decimal("100.00")
    billing_service.mark_sent(session, invoice)
    assert invoice.status == InvoiceStatus.SENT.value

    payment = billing_service.record_payment(
        session, tenant=tenant, amount=Decimal("40"), invoice=invoice,
    )
    assert isinstance(payment, Payment)
    assert invoice.amount_paid == Decimal("40.00")
    assert invoice.balance == Decimal("60.00")
    assert invoice.status == InvoiceStatus.SENT.value

    billing_service.record_payment(session, tenant=tenant, amount=Decimal("60"), invoice=invoice)
    assert invoice.balance == Decimal("0.00")
    assert invoice.status == InvoiceStatus.PAID.value
    assert billing_service.tenant_balance(session, tenant.id) == Decimal("0.00")


def test_unallocated_payment_applies_to_oldest_outstanding(session):
    tenant = make_tenant(session)
    plan = make_plan(session, tax_rate=Decimal("0"))
    subscription = billing_service.create_subscription(session, tenant, plan)
    invoice = billing_service.generate_invoice(
        session, tenant, subscription=subscription, plan=plan, include_setup_fee=False,
    )
    billing_service.mark_sent(session, invoice)

    billing_service.record_payment(session, tenant=tenant, amount=Decimal("25"))
    assert invoice.amount_paid == Decimal("25.00")
    assert billing_service.tenant_balance(session, tenant.id) == Decimal("75.00")


def test_draft_invoice_can_be_deleted_but_sent_cannot(session):
    tenant = make_tenant(session)
    plan = make_plan(session)
    invoice = billing_service.generate_invoice(session, tenant, plan=plan, include_setup_fee=False)
    billing_service.mark_sent(session, invoice)
    try:
        billing_service.delete_invoice(session, invoice)
    except billing_service.BillingError:
        pass
    else:  # pragma: no cover - must not happen
        raise AssertionError("sent invoices must not be deletable")

    draft = billing_service.generate_invoice(session, tenant, plan=plan, include_setup_fee=False)
    billing_service.delete_invoice(session, draft)
    assert session.get(Invoice, draft.id) is None


def test_credit_note_reduces_balance(session):
    tenant = make_tenant(session)
    plan = make_plan(session, tax_rate=Decimal("0"))
    invoice = billing_service.generate_invoice(session, tenant, plan=plan, include_setup_fee=False)
    billing_service.mark_sent(session, invoice)
    billing_service.create_credit_note(session, tenant=tenant, invoice=invoice, amount=Decimal("30"), reason="goodwill")
    assert billing_service.tenant_balance(session, tenant.id) == Decimal("70.00")


def test_overdue_and_late_fee(session):
    tenant = make_tenant(session)
    plan = make_plan(session, tax_rate=Decimal("0"))
    invoice = billing_service.generate_invoice(session, tenant, plan=plan, include_setup_fee=False)
    billing_service.mark_sent(session, invoice)
    invoice.due_date = date.today() - timedelta(days=3)
    settings_service.set_value(session, "late_fee_percent", "5")
    session.flush()

    changed = billing_service.mark_overdue(session, actor="tester")
    assert invoice in changed
    assert invoice.status == InvoiceStatus.OVERDUE.value
    assert invoice.late_fee == Decimal("5.00")


def test_mrr_normalises_yearly_plans(session):
    tenant = make_tenant(session)
    plan = make_plan(session, price_month=Decimal("100"), price_year=Decimal("1200"))
    billing_service.create_subscription(session, tenant, plan, cycle="monthly")
    # A second tenant on the yearly cycle.
    other = make_tenant(session, name="Beta", subdomain="beta", db_name="beta")
    billing_service.create_subscription(session, other, plan, cycle="yearly")
    # 100 + 1200/12 = 200
    assert billing_service.mrr(session) == Decimal("200.00")


def test_outstanding_and_overdue_totals(session):
    tenant = make_tenant(session)
    plan = make_plan(session, tax_rate=Decimal("0"))
    invoice = billing_service.generate_invoice(session, tenant, plan=plan, include_setup_fee=False)
    billing_service.mark_sent(session, invoice)
    assert billing_service.outstanding_total(session) == Decimal("100.00")
    invoice.due_date = date.today() - timedelta(days=1)
    session.flush()
    billing_service.mark_overdue(session)
    assert billing_service.overdue_total(session) == Decimal("100.00")
