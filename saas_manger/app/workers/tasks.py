"""Celery tasks: usage refresh, billing sweep, invoice generation, updates, backups."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import chord, group

from app.db import session_scope
from app.models.billing import Subscription
from app.models.enums import InvoiceStatus, SubscriptionStatus, TenantStatus
from app.models.tenant import Tenant
from app.services import (
    audit,
    backup_service,
    billing_service,
    provisioner,
    settings_service,
    tenant_service,
    update_service,
    usage as usage_service,
)
from app.workers.celery_app import celery_app

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
@celery_app.task(name="app.workers.tasks.refresh_all_usage")
def refresh_all_usage() -> dict[str, list[str]]:
    """Refresh the usage counters of every tenant."""
    with session_scope() as session:
        result = usage_service.refresh_all(session)
    _logger.info("usage refresh done for %d tenants", len(result))
    return result


@celery_app.task(name="app.workers.tasks.refresh_tenant_usage")
def refresh_tenant_usage(tenant_id: int) -> list[str]:
    with session_scope() as session:
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            return []
        return usage_service.refresh_tenant(session, tenant)


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------
@celery_app.task(name="app.workers.tasks.generate_due_invoices")
def generate_due_invoices() -> list[str]:
    """Create invoices for subscriptions whose next_invoice_date has arrived."""
    generated: list[str] = []
    today = date.today()
    with session_scope() as session:
        sub_ids = [
            sub.id for sub in session.query(Subscription).all()
            if sub.next_invoice_date and sub.next_invoice_date <= today
            and sub.status in (SubscriptionStatus.ACTIVE.value, SubscriptionStatus.PAST_DUE.value)
        ]
        for sub_id in sub_ids:
            subscription = session.get(Subscription, sub_id)
            tenant = session.get(Tenant, subscription.tenant_id)
            if tenant is None or tenant.status == TenantStatus.CANCELLED.value:
                continue
            invoice = billing_service.generate_invoice(session, tenant, subscription=subscription)
            billing_service.mark_sent(session, invoice, actor="scheduler")
            generated.append(invoice.number)
            _email_invoice(session, invoice, tenant)
    _logger.info("generated %d invoices", len(generated))
    return generated


def _email_invoice(session, invoice, tenant) -> None:
    """Email the invoice PDF to the tenant (best effort — never fatal)."""
    from app.services import email_service, invoice_pdf  # noqa: PLC0415

    try:
        company = settings_service.company_block(session)
        pdf = invoice_pdf.render_invoice_pdf(invoice, tenant, company)
        email_service.send_invoice_email(session, invoice, tenant, pdf_bytes=pdf,
                                         company=company, actor="scheduler")
    except Exception as exc:  # noqa: BLE001 - a mail failure must not break billing
        _logger.warning("invoice email failed for %s: %s", invoice.number, exc)


@celery_app.task(name="app.workers.tasks.daily_billing_sweep")
def daily_billing_sweep() -> dict[str, int]:
    """Overdue invoices, dunning, auto-suspend past grace, auto-expire, reactivation."""
    stats = {"overdue": 0, "reminded": 0, "suspended": 0, "expired": 0, "reactivated": 0}
    today = date.today()
    with session_scope() as session:
        if not settings_service.get_bool(session, "dunning_enabled", True):
            return stats

        # 1. Mark overdue + late fees.
        stats["overdue"] = len(billing_service.mark_overdue(session, today=today))

        grace_days = settings_service.get_int(session, "grace_days", 7)
        auto_suspend = settings_service.get_bool(session, "auto_suspend", True)
        auto_reactivate = settings_service.get_bool(session, "auto_reactivate", True)

        tenants = session.query(Tenant).all()
        for tenant in tenants:
            # 2. Expiry: past expiry_date and not a paying active subscription.
            if tenant.expiry_date and tenant.expiry_date < today and tenant.status in (
                TenantStatus.TRIAL.value, TenantStatus.ACTIVE.value,
            ):
                tenant.status = TenantStatus.EXPIRED.value
                _safe_push_status(tenant)
                audit.record(session, action="tenant.expired", actor="scheduler",
                             target_type="tenant", target_id=tenant.id, level="warning",
                             detail=f"expired on {tenant.expiry_date}")
                stats["expired"] += 1
                continue

            # 3. Auto-suspend when an invoice is overdue beyond the grace period.
            balance = billing_service.tenant_balance(session, tenant.id)
            if auto_suspend and balance > 0 and tenant.status == TenantStatus.ACTIVE.value:
                overdue = _oldest_overdue_days(session, tenant.id)
                if overdue is not None and overdue > grace_days:
                    tenant.maintenance_mode = True
                    tenant.status = TenantStatus.SUSPENDED.value
                    _safe_push_status(tenant)
                    audit.record(session, action="tenant.suspended", actor="scheduler",
                                 target_type="tenant", target_id=tenant.id, level="warning",
                                 detail=f"balance {balance} overdue {overdue} days")
                    stats["suspended"] += 1

            # 4. Auto-reactivate once the balance is cleared.
            if auto_reactivate and balance <= 0 and tenant.status == TenantStatus.SUSPENDED.value:
                tenant.maintenance_mode = False
                tenant.status = TenantStatus.ACTIVE.value
                _safe_push_status(tenant)
                audit.record(session, action="tenant.reactivated", actor="scheduler",
                             target_type="tenant", target_id=tenant.id,
                             detail="balance cleared")
                stats["reactivated"] += 1

        # 5. Reminders: before expiry and after an overdue invoice due date.
        remind_before = settings_service.get_int(session, "reminder_days_before", 7)
        remind_after = settings_service.get_int(session, "reminder_days_after", 3)
        stats["reminded"] = _record_expiry_reminders(session, today, remind_before)
        stats["reminded"] += _record_overdue_reminders(session, today, remind_after)

    _logger.info("daily billing sweep: %s", stats)
    return stats


def _oldest_overdue_days(session, tenant_id: int) -> int | None:
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.billing import Invoice  # noqa: PLC0415

    invoice = session.scalar(
        select(Invoice)
        .where(Invoice.tenant_id == tenant_id, Invoice.status == InvoiceStatus.OVERDUE.value)
        .order_by(Invoice.due_date)
    )
    if invoice is None:
        return None
    return (date.today() - invoice.due_date).days


def _record_expiry_reminders(session, today: date, days_before: int) -> int:
    """Record and email a reminder for tenants expiring within N days."""
    from sqlalchemy import select  # noqa: PLC0415

    from app.services import email_service  # noqa: PLC0415

    count = 0
    horizon = today + timedelta(days=days_before)
    tenants = session.scalars(
        select(Tenant)
        .where(Tenant.expiry_date.is_not(None))
        .where(Tenant.expiry_date <= horizon)
        .where(Tenant.expiry_date >= today)
    ).all()
    for tenant in tenants:
        audit.record(session, action="tenant.reminder", actor="scheduler",
                     target_type="tenant", target_id=tenant.id,
                     detail=f"expires on {tenant.expiry_date}")
        email_service.send_reminder_email(
            session, tenant,
            subject=f"Your subscription expires on {tenant.expiry_date:%Y-%m-%d}",
            body=(
                f"Dear {tenant.contact_name or tenant.name},\n\n"
                f"Your subscription expires on {tenant.expiry_date:%Y-%m-%d}.\n"
                "Please renew it to avoid any interruption of service.\n\n"
                "Thank you for your business."
            ),
            action="tenant.reminder_email",
        )
        count += 1
    return count


def _record_overdue_reminders(session, today: date, days_after: int) -> int:
    """Record and email a dunning reminder for invoices overdue by N days."""
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.billing import Invoice  # noqa: PLC0415
    from app.services import email_service  # noqa: PLC0415

    count = 0
    cutoff = today - timedelta(days=days_after)
    invoices = session.scalars(
        select(Invoice)
        .where(Invoice.status == InvoiceStatus.OVERDUE.value)
        .where(Invoice.due_date <= cutoff)
    ).all()
    for invoice in invoices:
        tenant = session.get(Tenant, invoice.tenant_id)
        if tenant is None:
            continue
        days_late = (today - invoice.due_date).days
        audit.record(session, action="invoice.reminder", actor="scheduler",
                     target_type="invoice", target_id=invoice.id, level="warning",
                     detail=f"{invoice.number} overdue {days_late} days")
        email_service.send_reminder_email(
            session, tenant,
            subject=f"Reminder: invoice {invoice.number} is overdue",
            body=(
                f"Dear {tenant.contact_name or tenant.name},\n\n"
                f"Invoice {invoice.number} was due on {invoice.due_date:%Y-%m-%d} "
                f"({days_late} days ago) and is still unpaid.\n\n"
                f"Amount due: {invoice.balance:,.2f} {invoice.currency}\n\n"
                "Please arrange payment to avoid any interruption of service.\n\n"
                "Thank you."
            ),
            action="invoice.reminder_email",
        )
        count += 1
    return count


def _safe_push_status(tenant: Tenant) -> None:
    try:
        tenant_service.push_status(tenant)
    except Exception as exc:  # noqa: BLE001 - client may be offline
        _logger.warning("could not push status for %s: %s", tenant.subdomain, exc)


# ---------------------------------------------------------------------------
# Updates
# ---------------------------------------------------------------------------
@celery_app.task(name="app.workers.tasks.run_update_job")
def run_update_job(job_id: int) -> str:
    """Process one database update job."""
    with session_scope() as session:
        return update_service.process_job(session, job_id)


@celery_app.task(name="app.workers.tasks.run_update_run")
def run_update_run(run_id: int) -> str:
    """Dispatch all pending jobs of a run, then finalize."""
    with session_scope() as session:
        job_ids = update_service.pending_job_ids(session, run_id)
    if not job_ids:
        with session_scope() as session:
            return update_service.finalize_run(session, run_id)
    # Bounded parallelism comes from the number of worker processes.
    chord(
        group(run_update_job.s(job_id) for job_id in job_ids),
        finalize_run_task.s(run_id),
    ).apply_async()
    return SubscriptionStatus.ACTIVE.value  # dispatched


@celery_app.task(name="app.workers.tasks.finalize_run")
def finalize_run_task(_results, run_id: int) -> str:
    with session_scope() as session:
        status = update_service.finalize_run(session, run_id)
        audit.record(session, action="update.run_finished", actor="scheduler",
                     target_type="update_run", target_id=run_id, detail=status)
    return status


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------
@celery_app.task(name="app.workers.tasks.backup_tenant")
def backup_tenant(tenant_id: int, reason: str = "scheduled") -> str:
    with session_scope() as session:
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            return ""
        backup = backup_service.create_backup(session, tenant, reason=reason)
        audit.record(session, action="backup.create", actor="scheduler",
                     target_type="tenant", target_id=tenant_id, detail=backup.path)
        return backup.path


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------
@celery_app.task(name="app.workers.tasks.provision_tenant")
def provision_tenant(tenant_id: int, admin_password: str, demo: bool = False) -> dict:
    with session_scope() as session:
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise ValueError(f"Unknown tenant {tenant_id}")
        result = provisioner.provision(session, tenant, admin_password=admin_password, demo=demo)
        audit.record(session, action="tenant.provisioned", actor="scheduler",
                     target_type="tenant", target_id=tenant_id,
                     detail=f"db={result.db_name} modules={len(result.installed_modules)}")
        return {"db_name": result.db_name, "modules": result.installed_modules}
