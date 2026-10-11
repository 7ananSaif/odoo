"""Outgoing email: configuration resolution, graceful no-op, and message bodies."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models.billing import Invoice
from app.models.ops import AuditLog
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.security import encrypt_secret
from app.services import billing_service, email_service, settings_service


def make_tenant(session, **kwargs) -> Tenant:
    tenant = Tenant(
        name=kwargs.get("name", "Acme Inc"),
        subdomain=kwargs.get("subdomain", "acme"),
        db_name=kwargs.get("db_name", "acme"),
        status="active",
        email=kwargs.get("email", "billing@acme.test"),
        contact_name=kwargs.get("contact_name", "Jane Doe"),
    )
    session.add(tenant)
    session.flush()
    return tenant


def make_invoice(session, tenant: Tenant) -> Invoice:
    plan = Plan(name="Standard", code="standard", price_month=Decimal("100"),
                price_year=Decimal("1000"), tax_rate=Decimal("0"), currency="USD")
    session.add(plan)
    session.flush()
    invoice = billing_service.generate_invoice(
        session, tenant, plan=plan, include_setup_fee=False,
    )
    billing_service.mark_sent(session, invoice)
    return invoice


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def test_mail_config_falls_back_to_env_when_disabled(session):
    settings_service.set_value(session, "email_enabled", "false")
    settings_service.set_value(session, "smtp_host", "")
    config = email_service.mail_config(session)
    assert config.enabled is False
    assert config.is_configured is False


def test_mail_config_reads_db_and_decrypts_password(session):
    settings_service.set_value(session, "email_enabled", "true")
    settings_service.set_value(session, "smtp_host", "smtp.test")
    settings_service.set_value(session, "smtp_port", "2525")
    settings_service.set_value(session, "smtp_user", "billing")
    settings_service.set_value(session, "email_from", "billing@acme.test")
    settings_service.set_value(session, "smtp_password", encrypt_secret("s3cret") or "")

    config = email_service.mail_config(session)
    assert config.is_configured is True
    assert config.host == "smtp.test"
    assert config.port == 2525
    assert config.password == "s3cret"


def test_send_mail_skips_when_unconfigured(session):
    settings_service.set_value(session, "email_enabled", "false")
    settings_service.set_value(session, "smtp_host", "")
    result = email_service.send_mail(
        email_service.mail_config(session), "someone@test", "Hi", "Body",
    )
    assert result.sent is False
    assert result.skipped_reason == "email not configured"


# ---------------------------------------------------------------------------
# Bodies
# ---------------------------------------------------------------------------
def test_invoice_body_and_subject(session):
    tenant = make_tenant(session)
    invoice = make_invoice(session, tenant)

    subject = email_service.invoice_subject(invoice, tenant, "My SaaS Company")
    body = email_service.invoice_body(invoice, tenant, "My SaaS Company")

    assert invoice.number in subject
    assert "My SaaS Company" in subject
    assert "Jane Doe" in body
    assert invoice.number in body
    assert "Amount due" in body


# ---------------------------------------------------------------------------
# Graceful behaviour when email is off
# ---------------------------------------------------------------------------
def test_send_invoice_email_is_a_logged_noop_when_disabled(session):
    settings_service.set_value(session, "email_enabled", "false")
    settings_service.set_value(session, "smtp_host", "")
    tenant = make_tenant(session)
    invoice = make_invoice(session, tenant)

    result = email_service.send_invoice_email(
        session, invoice, tenant, pdf_bytes=b"%PDF-1.4", company={"name": "Acme"}, actor="tester",
    )
    assert result.sent is False
    # The attempt is always recorded, even when the send was skipped.
    entry = session.scalar(select(AuditLog).where(AuditLog.action == "invoice.email.skipped"))
    assert entry is not None
    assert entry.actor == "tester"


def test_send_invoice_email_without_recipient_is_logged(session):
    tenant = make_tenant(session, email="")
    invoice = make_invoice(session, tenant)

    result = email_service.send_invoice_email(
        session, invoice, tenant, pdf_bytes=b"%PDF-1.4", company={}, actor="tester",
    )
    assert result.sent is False
    assert result.skipped_reason == "no email address"
    entry = session.scalar(
        select(AuditLog).where(AuditLog.action == "invoice.email.skipped", AuditLog.level == "warning")
    )
    assert entry is not None


def test_send_reminder_email_records_attempt(session):
    settings_service.set_value(session, "email_enabled", "false")
    settings_service.set_value(session, "smtp_host", "")
    tenant = make_tenant(session)
    result = email_service.send_reminder_email(
        session, tenant, subject="Renew soon", body="Please renew.", action="tenant.reminder_email",
    )
    assert result.sent is False
    entry = session.scalar(select(AuditLog).where(AuditLog.action == "tenant.reminder_email.skipped"))
    assert entry is not None


# ---------------------------------------------------------------------------
# Settings helpers reused by the emailer
# ---------------------------------------------------------------------------
def test_company_block_and_payment_methods(session):
    settings_service.set_value(session, "company_name", "Acme Billing")
    settings_service.set_value(session, "company_email", "billing@acme.test")
    settings_service.set_value(session, "payment_methods", "bank_transfer, cash")

    block = settings_service.company_block(session)
    assert block["name"] == "Acme Billing"
    assert block["email"] == "billing@acme.test"
    assert settings_service.payment_methods(session) == ["bank_transfer", "cash"]
