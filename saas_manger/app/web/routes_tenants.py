"""Tenant management: list, create, edit, lifecycle, limits, backups, modules."""
from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.deps import CurrentUser, SessionDep, client_ip
from app.models.billing import Invoice
from app.models.enums import TenantStatus
from app.models.ops import Backup
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.security import generate_token
from app.services import (
    audit,
    backup_service,
    billing_service,
    limits as limits_service,
    odoo_login,
    permissions,
    plan_service,
    provisioner,
    tenant_service,
    usage as usage_service,
)
from app.web import guards
from app.web.templating import render

router = APIRouter(prefix="/tenants", tags=["tenants"])

SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:63] or "tenant"


def _redirect(url: str, flash: str = "", error: str = "") -> RedirectResponse:
    from urllib.parse import urlencode  # noqa: PLC0415

    params = {}
    if flash:
        params["flash"] = flash
    if error:
        params["error"] = error
    suffix = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{url}{suffix}", status_code=303)


@router.get("", response_class=HTMLResponse)
def list_view(request: Request, session: SessionDep, user: CurrentUser, status: str = ""):
    tenants = tenant_service.list_tenants(session, status=status or None)
    totals = {t.id: billing_service.tenant_balance(session, t.id) for t in tenants}
    return render(request, "tenants/list.html", {
        "tenants": tenants, "balances": totals, "status_filter": status,
    })


@router.get("/new", response_class=HTMLResponse)
def new_form(request: Request, session: SessionDep, user: CurrentUser):
    plans = plan_service.list_plans(session, active_only=True)
    return render(request, "tenants/form.html", {"tenant": None, "plans": plans, "default_trial": _default_trial(session)})


def _default_trial(session) -> int:
    from app.services import settings_service  # noqa: PLC0415

    return settings_service.get_int(session, "trial_days", 14)


@router.post("/new")
def create(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    name: str = Form(...),
    subdomain: str = Form(""),
    plan_id: int = Form(0),
    contact_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    country: str = Form(""),
    tax_id: str = Form(""),
    trial_days: int = Form(0),
    provision_now: bool = Form(False),
    demo: bool = Form(False),
):
    """Create the tenant row (optionally provision the database immediately)."""
    if error := guards.permission_error(user, permissions.PERM_TENANTS_MANAGE, "create tenants"):
        return _redirect("/tenants/new", error=error)
    subdomain = (subdomain or _slugify(name)).strip().lower()
    if not SUBDOMAIN_RE.match(subdomain):
        return _redirect("/tenants/new", error="Invalid subdomain")
    if tenant_service.get_by_subdomain(session, subdomain):
        return _redirect("/tenants/new", error="Subdomain already used")

    plan = session.get(Plan, plan_id) if plan_id else None
    trial = trial_days or _default_trial(session)
    tenant = Tenant(
        name=name.strip(),
        subdomain=subdomain,
        db_name=subdomain,
        contact_name=contact_name,
        email=email,
        phone=phone,
        country=country,
        tax_id=tax_id,
        plan_id=plan.id if plan else None,
        status=TenantStatus.TRIAL.value,
        start_date=date.today(),
        expiry_date=date.today() + timedelta(days=trial),
        trial_days=trial,
        admin_login="admin",
    )
    if plan:
        tenant_service.apply_plan_limits(tenant, plan)
    session.add(tenant)
    session.flush()

    billing_service.create_subscription(session, tenant, plan)

    audit.record(session, action="tenant.create", actor=user.email, target_type="tenant",
                 target_id=tenant.id, ip=client_ip(request), detail=subdomain)
    session.commit()

    if provision_now:
        admin_password = generate_token(9)
        try:
            provisioner.provision(session, tenant, plan=plan, admin_password=admin_password, demo=demo)
            tenant_service.push_limits_to_database(tenant)
            session.commit()
            return _redirect(f"/tenants/{tenant.id}", flash=f"Tenant provisioned. Admin password: {admin_password}")
        except Exception as exc:  # noqa: BLE001
            session.commit()
            return _redirect(f"/tenants/{tenant.id}", error=f"Provisioning failed: {exc}")

    return _redirect(f"/tenants/{tenant.id}", flash="Tenant created")


@router.get("/{tenant_id}", response_class=HTMLResponse)
def detail(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int):
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    backups = backup_service.list_backups(session, tenant.id)
    balance = billing_service.tenant_balance(session, tenant.id)
    invoices = list(
        session.query(Invoice)
        .filter_by(tenant_id=tenant.id)
        .order_by(Invoice.issue_date.desc())
        .all()
    )
    percentages = {
        key: tenant.usage_percent(key)
        for key in ("users", "warehouses", "companies", "storage", "db_size")
    }
    return render(request, "tenants/detail.html", {
        "tenant": tenant, "backups": backups, "balance": balance,
        "invoices": invoices, "percentages": percentages,
    })


@router.get("/{tenant_id}/edit", response_class=HTMLResponse)
def edit_form(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int):
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    return render(request, "tenants/form.html", {
        "tenant": tenant, "plans": plan_service.list_plans(session, active_only=True),
        "default_trial": tenant.trial_days,
    })


@router.post("/{tenant_id}/edit")
def update(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: int,
    name: str = Form(...),
    contact_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    country: str = Form(""),
    tax_id: str = Form(""),
    notes: str = Form(""),
    plan_id: int = Form(0),
    status: str = Form(""),
    expiry_date: str = Form(""),
    auto_renew: bool = Form(False),
    max_users: int = Form(0),
    max_warehouses: int = Form(0),
    max_companies: int = Form(0),
    max_storage_mb: int = Form(0),
    max_db_size_mb: int = Form(0),
    count_portal_users: bool = Form(False),
    block_writes: bool = Form(False),
    push_now: bool = Form(False),
):
    """Update tenant identity, plan, limits (with downgrade protection) and status."""
    if error := guards.permission_error(user, permissions.PERM_TENANTS_MANAGE, "edit tenants"):
        return _redirect(f"/tenants/{tenant_id}/edit", error=error)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")

    new_limits = {
        "max_users": max_users, "max_warehouses": max_warehouses, "max_companies": max_companies,
        "max_storage_mb": max_storage_mb, "max_db_size_mb": max_db_size_mb,
    }
    try:
        plan_service.assert_downgrade_allowed(tenant, new_limits)
    except plan_service.PlanError as exc:
        return _redirect(f"/tenants/{tenant.id}/edit", error=str(exc))

    tenant.name = name.strip()
    tenant.contact_name = contact_name
    tenant.email = email
    tenant.phone = phone
    tenant.country = country
    tenant.tax_id = tax_id
    tenant.notes = notes
    tenant.auto_renew = auto_renew
    # Enforcement toggles pushed into the client database as saas.* parameters.
    tenant.count_portal_users = count_portal_users
    tenant.block_writes = block_writes

    plan = session.get(Plan, plan_id) if plan_id else None
    plan_changed = plan and plan.id != tenant.plan_id
    tenant.plan_id = plan.id if plan else None

    for key, value in new_limits.items():
        setattr(tenant, key, value)

    if status and status != tenant.status:
        tenant.status = status
        tenant.maintenance_mode = status == TenantStatus.SUSPENDED.value

    if expiry_date:
        try:
            tenant.expiry_date = date.fromisoformat(expiry_date)
        except ValueError:
            return _redirect(f"/tenants/{tenant.id}/edit", error="Invalid expiry date")

    audit.record(session, action="tenant.update", actor=user.email, target_type="tenant",
                 target_id=tenant.id, ip=client_ip(request))
    session.commit()

    if plan_changed:
        _apply_plan_change(session, tenant, plan, user.email)
    if push_now:
        try:
            payload = tenant_service.push_limits_to_database(tenant)
            audit.record(session, action="tenant.push_limits", actor=user.email, target_type="tenant",
                         target_id=tenant.id, detail=limits_service.dumps(payload))
            session.commit()
        except Exception as exc:  # noqa: BLE001
            return _redirect(f"/tenants/{tenant.id}", error=f"Push failed: {exc}")
    return _redirect(f"/tenants/{tenant.id}", flash="Tenant updated")


def _apply_plan_change(session, tenant: Tenant, plan: Plan | None, actor: str) -> None:
    """Install/uninstall apps to match a new plan and push the new limits."""
    try:
        client = tenant_service.authenticated_client(tenant)
        try:
            diff = plan_service.apply_plan(client, plan)
            limits_service.push_limits(client, tenant)
        finally:
            client.close()
        audit.record(session, action="tenant.plan_applied", actor=actor, target_type="tenant",
                     target_id=tenant.id,
                     detail=f"+{diff.to_install} -{diff.to_uninstall}")
    except Exception as exc:  # noqa: BLE001
        audit.record(session, action="tenant.plan_apply_failed", actor=actor, target_type="tenant",
                     target_id=tenant.id, level="error", detail=str(exc))
    session.commit()


@router.post("/{tenant_id}/provision")
def provision_now(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int, demo: bool = Form(False)):
    """Provision a tenant database that was created without one."""
    if error := guards.permission_error(user, permissions.PERM_TENANTS_MANAGE, "provision databases"):
        return _redirect(f"/tenants/{tenant_id}", error=error)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    admin_password = generate_token(9)
    try:
        provisioner.provision(session, tenant, admin_password=admin_password, demo=demo)
        tenant_service.push_limits_to_database(tenant)
        session.commit()
        return _redirect(f"/tenants/{tenant.id}", flash=f"Provisioned. Admin password: {admin_password}")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        return _redirect(f"/tenants/{tenant.id}", error=f"Provisioning failed: {exc}")


@router.post("/{tenant_id}/push-limits")
def push_limits(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int):
    """Write the current limits / status into the client database."""
    if error := guards.permission_error(user, permissions.PERM_TENANTS_MANAGE, "push limits"):
        return _redirect(f"/tenants/{tenant_id}", error=error)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    try:
        payload = tenant_service.push_limits_to_database(tenant)
        audit.record(session, action="tenant.push_limits", actor=user.email, target_type="tenant",
                     target_id=tenant.id, ip=client_ip(request), detail=limits_service.dumps(payload))
        session.commit()
        return _redirect(f"/tenants/{tenant.id}", flash="Limits pushed to the database")
    except Exception as exc:  # noqa: BLE001
        return _redirect(f"/tenants/{tenant.id}", error=f"Push failed: {exc}")


@router.post("/{tenant_id}/refresh-usage")
def refresh_usage(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int):
    if error := guards.permission_error(user, permissions.PERM_TENANTS_MANAGE, "refresh usage"):
        return _redirect(f"/tenants/{tenant_id}", error=error)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    warnings = usage_service.refresh_tenant(session, tenant)
    session.commit()
    return _redirect(f"/tenants/{tenant.id}", flash=f"Usage refreshed ({len(warnings)} alerts)")


@router.post("/{tenant_id}/suspend")
def suspend(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int):
    if error := guards.permission_error(user, permissions.PERM_TENANTS_MANAGE, "suspend tenants"):
        return _redirect(f"/tenants/{tenant_id}", error=error)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    try:
        provisioner.suspend(session, tenant)
        audit.record(session, action="tenant.suspend", actor=user.email, target_type="tenant",
                     target_id=tenant.id, ip=client_ip(request))
        session.commit()
        return _redirect(f"/tenants/{tenant.id}", flash="Tenant suspended")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        return _redirect(f"/tenants/{tenant.id}", error=f"Suspend failed: {exc}")


@router.post("/{tenant_id}/activate")
def activate(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int):
    if error := guards.permission_error(user, permissions.PERM_TENANTS_MANAGE, "activate tenants"):
        return _redirect(f"/tenants/{tenant_id}", error=error)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    try:
        provisioner.activate(session, tenant)
        audit.record(session, action="tenant.activate", actor=user.email, target_type="tenant",
                     target_id=tenant.id, ip=client_ip(request))
        session.commit()
        return _redirect(f"/tenants/{tenant.id}", flash="Tenant activated")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        return _redirect(f"/tenants/{tenant.id}", error=f"Activation failed: {exc}")


@router.post("/{tenant_id}/backup")
def backup(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int):
    if error := guards.permission_error(user, permissions.PERM_BACKUPS_MANAGE, "create backups"):
        return _redirect(f"/tenants/{tenant_id}", error=error)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    try:
        record = backup_service.create_backup(session, tenant, reason="manual")
        audit.record(session, action="backup.create", actor=user.email, target_type="tenant",
                     target_id=tenant.id, ip=client_ip(request), detail=record.path)
        session.commit()
        return _redirect(f"/tenants/{tenant.id}", flash=f"Backup created: {record.path}")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        return _redirect(f"/tenants/{tenant.id}", error=f"Backup failed: {exc}")


@router.post("/{tenant_id}/restore/{backup_id}")
def restore(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int, backup_id: int):
    if error := guards.permission_error(user, permissions.PERM_BACKUPS_MANAGE, "restore backups"):
        return _redirect(f"/tenants/{tenant_id}", error=error)
    tenant = session.get(Tenant, tenant_id)
    record = session.get(Backup, backup_id)
    if tenant is None or record is None:
        raise HTTPException(404, "Not found")
    try:
        backup_service.restore_backup(session, tenant, record)
        audit.record(session, action="backup.restore", actor=user.email, target_type="tenant",
                     target_id=tenant.id, ip=client_ip(request), level="warning", detail=record.path)
        session.commit()
        return _redirect(f"/tenants/{tenant.id}", flash="Restore finished")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        return _redirect(f"/tenants/{tenant.id}", error=f"Restore failed: {exc}")


@router.post("/{tenant_id}/test-odoo")
def test_odoo(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int):
    """Verify the manager can reach this tenant's Odoo and summarise what it sees."""
    if error := guards.permission_error(user, permissions.PERM_TENANTS_MANAGE, "test Odoo connections"):
        return _redirect(f"/tenants/{tenant_id}", error=error)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    if not tenant.provisioned:
        return _redirect(f"/tenants/{tenant.id}", error="This tenant has no database yet — provision it first")

    try:
        client = tenant_service.authenticated_client(tenant)
    except Exception as exc:  # noqa: BLE001
        return _redirect(f"/tenants/{tenant.id}", error=f"Odoo connection failed: {exc}")

    try:
        version = client.server_version() or "unknown"
        user_count = client.call_kw("res.users", "search_count", [[]])
        module_count = len(client.installed_modules())
        companies = client.call_kw("res.company", "search_read", [[], ["name"]], {"limit": 1})
    except Exception as exc:  # noqa: BLE001
        return _redirect(f"/tenants/{tenant.id}", error=f"Odoo call failed: {exc}")
    finally:
        client.close()

    company = companies[0]["name"] if companies else "—"
    audit.record(session, action="tenant.test_odoo", actor=user.email, target_type="tenant",
                 target_id=tenant.id, ip=client_ip(request),
                 detail=f"version={version} users={user_count} modules={module_count}")
    session.commit()
    return _redirect(
        f"/tenants/{tenant.id}",
        flash=f"Odoo {version} reachable · {user_count} users · {module_count} apps installed "
              f"· company {company}",
    )


@router.get("/{tenant_id}/open")
def open_in_odoo(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int):
    """Sign the browser straight into the tenant's Odoo (session hand-off).

    The manager authenticates server-side, then hands the resulting Odoo
    ``session_id`` to the browser as a cookie and redirects it to Odoo.  This
    works when the manager and Odoo share a host or a registrable domain (see
    :mod:`app.services.odoo_login`); otherwise the caller is asked to sign in
    manually instead.
    """
    if error := guards.permission_error(user, permissions.PERM_TENANTS_MANAGE, "open Odoo"):
        return _redirect(f"/tenants/{tenant_id}", error=error)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    if not tenant.provisioned:
        return _redirect(f"/tenants/{tenant.id}", error="This tenant has no database yet — provision it first")

    target = settings.tenant_browser_url(tenant.subdomain, tenant.db_name)
    odoo_host = urlparse(target).hostname or ""
    cookie_domain = odoo_login.cookie_domain_for(request.url.hostname or "", odoo_host)
    if cookie_domain is None:
        audit.record(session, action="tenant.open_odoo", actor=user.email, target_type="tenant",
                     target_id=tenant.id, ip=client_ip(request), level="warning",
                     detail="auto-login unavailable: unrelated domains")
        session.commit()
        return _redirect(
            f"/tenants/{tenant.id}",
            error="Auto-login is not possible between these domains — open Odoo and sign in "
                  "with the tenant admin account instead.",
        )

    try:
        session_id = tenant_service.open_browser_session(tenant)
    except Exception as exc:  # noqa: BLE001
        return _redirect(f"/tenants/{tenant.id}", error=f"Could not open Odoo: {exc}")

    audit.record(session, action="tenant.open_odoo", actor=user.email, target_type="tenant",
                 target_id=tenant.id, ip=client_ip(request), detail=f"db={tenant.db_name}")
    session.commit()

    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        odoo_login.SESSION_COOKIE,
        session_id,
        path="/",
        domain=(cookie_domain or None),
        httponly=True,
        samesite="lax",
        secure=target.startswith("https://"),
    )
    return response


@router.post("/{tenant_id}/delete")
def delete(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int,
           confirm: str = Form(""), drop_database: bool = Form(False)):
    """Delete a tenant row (and optionally drop its database)."""
    if error := guards.permission_error(user, permissions.PERM_TENANTS_DELETE, "delete tenants"):
        return _redirect(f"/tenants/{tenant_id}", error=error)
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    if confirm != tenant.subdomain:
        return _redirect(f"/tenants/{tenant.id}", error="Confirmation text does not match")
    if drop_database:
        try:
            provisioner.delete(session, tenant)
        except Exception as exc:  # noqa: BLE001
            return _redirect(f"/tenants/{tenant.id}", error=f"Drop failed: {exc}")
    name = tenant.subdomain
    audit.record(session, action="tenant.delete", actor=user.email, target_type="tenant",
                 target_id=tenant_id, ip=client_ip(request), level="warning",
                 detail=f"db_dropped={drop_database} {name}")
    session.delete(tenant)
    session.commit()
    return _redirect("/tenants", flash=f"Tenant {name} deleted")


@router.post("/{tenant_id}/duplicate")
def duplicate(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int,
              subdomain: str = Form(...)):
    if error := guards.permission_error(user, permissions.PERM_TENANTS_MANAGE, "duplicate tenants"):
        return _redirect(f"/tenants/{tenant_id}", error=error)
    source = session.get(Tenant, tenant_id)
    if source is None:
        raise HTTPException(404, "Tenant not found")
    subdomain = subdomain.strip().lower()
    if not SUBDOMAIN_RE.match(subdomain) or tenant_service.get_by_subdomain(session, subdomain):
        return _redirect(f"/tenants/{source.id}", error="Invalid or taken subdomain")
    try:
        clone = provisioner.duplicate(session, source, subdomain=subdomain, db_name=subdomain)
        billing_service.create_subscription(session, clone, clone.plan)
        audit.record(session, action="tenant.duplicate", actor=user.email, target_type="tenant",
                     target_id=clone.id, ip=client_ip(request), detail=f"from {source.subdomain}")
        session.commit()
        return _redirect(f"/tenants/{clone.id}", flash="Tenant duplicated")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        return _redirect(f"/tenants/{source.id}", error=f"Duplicate failed: {exc}")
