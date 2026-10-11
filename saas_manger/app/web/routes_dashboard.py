"""Dashboard: KPIs, expiring subscriptions, usage alerts, finance summary, export."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import func, select

from app.deps import CurrentUser, SessionDep
from app.models.billing import Invoice, Subscription
from app.models.enums import InvoiceStatus, TenantStatus
from app.models.tenant import Tenant
from app.services import billing_service, tenant_service
from app.web.templating import render

router = APIRouter(tags=["dashboard"])


def _counts(session: SessionDep) -> dict[str, int]:
    rows = session.execute(
        select(Tenant.status, func.count(Tenant.id)).group_by(Tenant.status)
    ).all()
    counts = {status.value: 0 for status in TenantStatus}
    for status, count in rows:
        counts[status] = count
    counts["total"] = sum(counts[s.value] for s in TenantStatus)
    return counts


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: SessionDep, user: CurrentUser):
    """Main overview page."""
    counts = _counts(session)
    expiring = tenant_service.expiring_soon(session, within_days=30)

    alerts: list[str] = []
    for tenant in session.scalars(select(Tenant)).all():
        alerts.extend(billing_service_alerts(tenant))

    metrics = {
        "mrr": billing_service.mrr(session),
        "outstanding": billing_service.outstanding_total(session),
        "overdue": billing_service.overdue_total(session),
        "yearly": billing_service.yearly_revenue(session, date.today().year),
        "revenue_per_plan": billing_service.revenue_per_plan(session),
    }
    recent_invoices = list(session.scalars(
        select(Invoice).order_by(Invoice.created_at.desc()).limit(8)
    ).all())
    recent_tenants = list(session.scalars(
        select(Tenant).order_by(Tenant.created_at.desc()).limit(8)
    ).all())

    return render(request, "dashboard.html", {
        "counts": counts,
        "expiring": expiring,
        "alerts": alerts,
        "metrics": metrics,
        "recent_invoices": recent_invoices,
        "recent_tenants": recent_tenants,
    })


def billing_service_alerts(tenant: Tenant) -> list[str]:
    """Return the >80% alerts for a tenant (dashboard banner list)."""
    from app.services import usage  # noqa: PLC0415

    return usage.alert_messages(tenant)


@router.get("/export/dashboard.csv")
def export_dashboard(session: SessionDep, user: CurrentUser):
    """Export the tenant list + usage + balances as CSV."""
    import csv
    import io  # noqa: PLC0415

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "name", "subdomain", "db_name", "status", "plan",
        "users", "warehouses", "companies", "db_size_mb",
        "max_users", "max_warehouses", "max_companies",
        "expiry_date", "balance",
    ])
    for tenant in tenant_service.list_tenants(session):
        writer.writerow([
            tenant.name, tenant.subdomain, tenant.db_name, tenant.status,
            tenant.plan.name if tenant.plan else "",
            tenant.current_users, tenant.current_warehouses, tenant.current_companies,
            tenant.current_db_size_mb,
            tenant.max_users, tenant.max_warehouses, tenant.max_companies,
            tenant.expiry_date or "", billing_service.tenant_balance(session, tenant.id),
        ])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dashboard.csv"},
    )
