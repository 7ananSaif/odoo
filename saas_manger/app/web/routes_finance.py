"""Finance: subscriptions, invoices, payments, credit notes, reports and exports."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select

from app.deps import CurrentUser, SessionDep, client_ip
from app.models.billing import CreditNote, Invoice, Payment, Subscription
from app.models.enums import BillingCycle, InvoiceStatus, PaymentMethod
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.services import audit, billing_service, invoice_pdf, settings_service
from app.web.templating import render

router = APIRouter(prefix="/finance", tags=["finance"])


def _redirect(url: str, flash: str = "", error: str = "") -> RedirectResponse:
    from urllib.parse import urlencode  # noqa: PLC0415

    params = {}
    if flash:
        params["flash"] = flash
    if error:
        params["error"] = error
    suffix = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{url}{suffix}", status_code=303)


def _decimal(value: str | None, default: str = "0") -> Decimal:
    try:
        return Decimal((value or default).strip() or default)
    except (InvalidOperation, AttributeError):
        return Decimal(default)


def _company_block(session) -> dict[str, str]:
    """Company details for invoices (delegated to the settings service)."""
    return settings_service.company_block(session)


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
@router.get("", response_class=HTMLResponse)
def overview(request: Request, session: SessionDep, user: CurrentUser):
    invoices = list(session.scalars(select(Invoice).order_by(Invoice.issue_date.desc()).limit(50)).all())
    subscriptions = list(session.scalars(select(Subscription).order_by(Subscription.id.desc()).limit(50)).all())
    tenants = {t.id: t for t in session.scalars(select(Tenant)).all()}
    return render(request, "finance/overview.html", {
        "invoices": invoices,
        "subscriptions": subscriptions,
        "tenants": tenants,
        "mrr": billing_service.mrr(session),
        "outstanding": billing_service.outstanding_total(session),
        "overdue": billing_service.overdue_total(session),
        "yearly": billing_service.yearly_revenue(session, date.today().year),
    })


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------
@router.post("/subscriptions/new")
def create_subscription(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: int = Form(...),
    plan_id: int = Form(0),
    cycle: str = Form(BillingCycle.MONTHLY.value),
    discount_percent: str = Form("0"),
    discount_fixed: str = Form("0"),
    tax_rate: str = Form("0"),
    payment_terms_days: int = Form(15),
):
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    plan = session.get(Plan, plan_id) if plan_id else tenant.plan
    subscription = billing_service.create_subscription(
        session, tenant, plan, cycle=cycle,
        tax_rate=_decimal(tax_rate), payment_terms_days=payment_terms_days,
    )
    subscription.discount_percent = _decimal(discount_percent)
    subscription.discount_fixed = _decimal(discount_fixed)
    audit.record(session, action="subscription.create", actor=user.email, target_type="tenant",
                 target_id=tenant.id, ip=client_ip(request), detail=cycle)
    session.commit()
    return _redirect("/finance", flash="Subscription created")


@router.post("/subscriptions/{subscription_id}/generate-invoice")
def generate_invoice(request: Request, session: SessionDep, user: CurrentUser, subscription_id: int):
    subscription = session.get(Subscription, subscription_id)
    if subscription is None:
        raise HTTPException(404, "Subscription not found")
    tenant = session.get(Tenant, subscription.tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    invoice = billing_service.generate_invoice(session, tenant, subscription=subscription)
    audit.record(session, action="invoice.generate_manual", actor=user.email, target_type="invoice",
                 target_id=invoice.id, ip=client_ip(request), detail=invoice.number)
    session.commit()
    return _redirect(f"/finance/invoices/{invoice.id}", flash=f"Draft invoice {invoice.number} created")


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------
@router.get("/invoices/{invoice_id}", response_class=HTMLResponse)
def invoice_detail(request: Request, session: SessionDep, user: CurrentUser, invoice_id: int):
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(404, "Invoice not found")
    tenant = session.get(Tenant, invoice.tenant_id)
    payments = list(session.scalars(select(Payment).where(Payment.invoice_id == invoice.id)).all())
    return render(request, "finance/invoice_detail.html", {
        "invoice": invoice, "tenant": tenant, "payments": payments,
        "methods": [m.value for m in PaymentMethod],
    })


@router.post("/invoices/{invoice_id}/send")
def send_invoice(request: Request, session: SessionDep, user: CurrentUser, invoice_id: int):
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(404, "Invoice not found")
    try:
        billing_service.mark_sent(session, invoice, actor=user.email)
        session.commit()
        return _redirect(f"/finance/invoices/{invoice.id}", flash="Invoice marked as sent")
    except billing_service.BillingError as exc:
        return _redirect(f"/finance/invoices/{invoice.id}", error=str(exc))


@router.post("/invoices/{invoice_id}/cancel")
def cancel_invoice(request: Request, session: SessionDep, user: CurrentUser, invoice_id: int):
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(404, "Invoice not found")
    billing_service.cancel_invoice(session, invoice, actor=user.email)
    session.commit()
    return _redirect(f"/finance/invoices/{invoice.id}", flash="Invoice cancelled")


@router.post("/invoices/{invoice_id}/delete")
def delete_invoice(request: Request, session: SessionDep, user: CurrentUser, invoice_id: int):
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(404, "Invoice not found")
    try:
        billing_service.delete_invoice(session, invoice)
        session.commit()
        return _redirect("/finance", flash="Draft invoice deleted")
    except billing_service.BillingError as exc:
        return _redirect(f"/finance/invoices/{invoice_id}", error=str(exc))


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf_view(request: Request, session: SessionDep, user: CurrentUser, invoice_id: int):
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(404, "Invoice not found")
    tenant = session.get(Tenant, invoice.tenant_id)
    pdf = invoice_pdf.render_invoice_pdf(invoice, tenant, _company_block(session))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={invoice.number}.pdf"},
    )


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
@router.post("/invoices/{invoice_id}/pay")
def record_payment(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    invoice_id: int,
    amount: str = Form(...),
    method: str = Form(PaymentMethod.BANK_TRANSFER.value),
    reference: str = Form(""),
    notes: str = Form(""),
    on_date: str = Form(""),
):
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(404, "Invoice not found")
    tenant = session.get(Tenant, invoice.tenant_id)
    parsed_date = None
    if on_date:
        try:
            parsed_date = date.fromisoformat(on_date)
        except ValueError:
            return _redirect(f"/finance/invoices/{invoice.id}", error="Invalid payment date")
    try:
        billing_service.record_payment(
            session, tenant=tenant, amount=_decimal(amount), method=method,
            reference=reference, invoice=invoice, on_date=parsed_date,
            notes=notes, actor=user.email,
        )
        session.commit()
        return _redirect(f"/finance/invoices/{invoice.id}", flash="Payment recorded")
    except billing_service.BillingError as exc:
        return _redirect(f"/finance/invoices/{invoice.id}", error=str(exc))


@router.post("/tenants/{tenant_id}/pay")
def record_tenant_payment(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: int,
    amount: str = Form(...),
    method: str = Form(PaymentMethod.BANK_TRANSFER.value),
    reference: str = Form(""),
    notes: str = Form(""),
):
    """Record an unallocated payment (auto-applied to the oldest invoice)."""
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    try:
        billing_service.record_payment(
            session, tenant=tenant, amount=_decimal(amount), method=method,
            reference=reference, notes=notes, actor=user.email,
        )
        session.commit()
        return _redirect(f"/tenants/{tenant.id}", flash="Payment recorded")
    except billing_service.BillingError as exc:
        return _redirect(f"/tenants/{tenant.id}", error=str(exc))


# ---------------------------------------------------------------------------
# Credit notes
# ---------------------------------------------------------------------------
@router.post("/invoices/{invoice_id}/credit-note")
def create_credit_note(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    invoice_id: int,
    amount: str = Form(...),
    reason: str = Form(""),
):
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(404, "Invoice not found")
    tenant = session.get(Tenant, invoice.tenant_id)
    note = billing_service.create_credit_note(
        session, tenant=tenant, invoice=invoice, amount=_decimal(amount),
        reason=reason, actor=user.email,
    )
    session.commit()
    return _redirect(f"/finance/invoices/{invoice.id}", flash=f"Credit note {note.number} issued")


# ---------------------------------------------------------------------------
# Reports / export
# ---------------------------------------------------------------------------
@router.get("/reports", response_class=HTMLResponse)
def reports(request: Request, session: SessionDep, user: CurrentUser):
    return render(request, "finance/reports.html", {
        "mrr": billing_service.mrr(session),
        "outstanding": billing_service.outstanding_total(session),
        "overdue": billing_service.overdue_total(session),
        "yearly": billing_service.yearly_revenue(session, date.today().year),
        "per_plan": billing_service.revenue_per_plan(session),
        "expiring": billing_service.expiring_subscriptions(session, within_days=30),
        "expired": billing_service.expired_subscriptions(session),
        "churn": billing_service.churn_stats(session, months=12),
    })


@router.get("/reports/invoices.xlsx")
def export_invoices_xlsx(session: SessionDep, user: CurrentUser):
    """Export every invoice as an Excel workbook."""
    from io import BytesIO  # noqa: PLC0415

    from openpyxl import Workbook  # noqa: PLC0415

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Invoices"
    sheet.append(["Number", "Tenant", "Status", "Issue date", "Due date", "Currency",
                  "Subtotal", "Discount", "Tax", "Late fee", "Total", "Paid", "Balance"])
    for invoice in session.scalars(select(Invoice).order_by(Invoice.issue_date)).all():
        tenant = session.get(Tenant, invoice.tenant_id)
        sheet.append([
            invoice.number, tenant.name if tenant else "", invoice.status,
            invoice.issue_date, invoice.due_date, invoice.currency,
            float(invoice.subtotal), float(invoice.discount_total), float(invoice.tax_total),
            float(invoice.late_fee), float(invoice.total), float(invoice.amount_paid),
            float(invoice.balance),
        ])
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=invoices.xlsx"},
    )


@router.get("/reports/payments.csv")
def export_payments_csv(session: SessionDep, user: CurrentUser):
    """Export every payment as CSV."""
    import csv
    from io import StringIO  # noqa: PLC0415

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Date", "Tenant", "Invoice", "Amount", "Currency", "Method", "Reference"])
    for payment in session.scalars(select(Payment).order_by(Payment.date)).all():
        tenant = session.get(Tenant, payment.tenant_id)
        invoice = session.get(Invoice, payment.invoice_id) if payment.invoice_id else None
        writer.writerow([
            payment.date, tenant.name if tenant else "", invoice.number if invoice else "",
            payment.amount, payment.currency, payment.method, payment.reference,
        ])
    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=payments.csv"},
    )


@router.post("/mark-overdue")
def run_overdue(request: Request, session: SessionDep, user: CurrentUser):
    changed = billing_service.mark_overdue(session, actor=user.email)
    session.commit()
    return _redirect("/finance", flash=f"{len(changed)} invoice(s) moved to overdue")


@router.post("/invoices/{invoice_id}/email")
def email_invoice(request: Request, session: SessionDep, user: CurrentUser, invoice_id: int):
    """Email the invoice PDF to the tenant's billing contact."""
    from app.services import email_service  # noqa: PLC0415

    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(404, "Invoice not found")
    tenant = session.get(Tenant, invoice.tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")

    company = settings_service.company_block(session)
    pdf = invoice_pdf.render_invoice_pdf(invoice, tenant, company)
    result = email_service.send_invoice_email(
        session, invoice, tenant, pdf_bytes=pdf, company=company, actor=user.email,
    )
    session.commit()
    if result.sent:
        return _redirect(f"/finance/invoices/{invoice.id}", flash=f"Invoice emailed to {tenant.email}")
    return _redirect(f"/finance/invoices/{invoice.id}",
                    error=f"Email not sent ({result.skipped_reason or 'unknown reason'})")


@router.post("/invoices/{invoice_id}/debit-note")
def create_debit_note(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    invoice_id: int,
    amount: str = Form(...),
    reason: str = Form(""),
):
    """Issue a debit note (extra charge) against an invoice."""
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(404, "Invoice not found")
    tenant = session.get(Tenant, invoice.tenant_id)
    try:
        note = billing_service.create_debit_note(
            session, tenant=tenant, invoice=invoice, amount=_decimal(amount),
            reason=reason, actor=user.email,
        )
    except billing_service.BillingError as exc:
        return _redirect(f"/finance/invoices/{invoice.id}", error=str(exc))
    session.commit()
    return _redirect(f"/finance/invoices/{invoice.id}", flash=f"Debit note {note.number} issued")


@router.post("/tenants/{tenant_id}/deposit")
def record_deposit(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: int,
    amount: str = Form(...),
    method: str = Form(PaymentMethod.BANK_TRANSFER.value),
    reference: str = Form(""),
    notes: str = Form(""),
):
    """Record a deposit received in advance (not tied to an invoice)."""
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    try:
        billing_service.record_deposit(
            session, tenant=tenant, amount=_decimal(amount), method=method,
            reference=reference, notes=notes, actor=user.email,
        )
    except billing_service.BillingError as exc:
        return _redirect(f"/tenants/{tenant.id}", error=str(exc))
    session.commit()
    return _redirect(f"/tenants/{tenant.id}", flash="Deposit recorded")


@router.post("/tenants/{tenant_id}/refund")
def record_refund(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: int,
    amount: str = Form(...),
    method: str = Form(PaymentMethod.BANK_TRANSFER.value),
    reference: str = Form(""),
    notes: str = Form(""),
):
    """Record a refund paid back to the tenant."""
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    try:
        billing_service.record_refund(
            session, tenant=tenant, amount=_decimal(amount), method=method,
            reference=reference, notes=notes, actor=user.email,
        )
    except billing_service.BillingError as exc:
        return _redirect(f"/tenants/{tenant.id}", error=str(exc))
    session.commit()
    return _redirect(f"/tenants/{tenant.id}", flash="Refund recorded")
