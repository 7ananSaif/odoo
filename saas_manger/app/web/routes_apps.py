"""Apps: the Odoo apps (modules) a tenant runs inside its own database.

Odoo's own Apps screen is hidden inside tenant databases by
``saas_tenant_guard``, because installing and removing apps is the provider's
decision, not the tenant's. This is where that decision is made: pick a tenant,
see the apps it runs, install the ones its plan allows and remove the rest.

Reads need ``apps.view`` (enforced at the router in :mod:`app.main`); every
change needs ``apps.manage`` and is checked again in the handlers below. Which
apps a tenant may install is decided by its plan (a.k.a. bouquet — see
:mod:`app.services.plan_service`), and every change is written to the audit log.

The Docker containers behind the stack are a different screen: see
:mod:`app.web.routes_containers`.
"""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.deps import CurrentUser, SessionDep, client_ip
from app.models.tenant import Tenant
from app.services import audit, odoo_apps, permissions, tenant_service
from app.web import guards
from app.web.templating import render

router = APIRouter(prefix="/apps", tags=["apps"])

#: The filter values the module list accepts.
FILTERS = ("installed", "plan", "apps", "all")


def _redirect(url: str, flash: str = "", error: str = "") -> RedirectResponse:
    from urllib.parse import urlencode  # noqa: PLC0415

    params = {}
    if flash:
        params["flash"] = flash
    if error:
        params["error"] = error
    suffix = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{url}{suffix}", status_code=303)


def _manage_error(user) -> str:
    """The error to show when ``user`` may not change a tenant's apps, else ``""``."""
    return guards.permission_error(user, permissions.PERM_APPS_MANAGE, "manage tenant apps")


def _tenant_or_404(session, tenant_id: int) -> Tenant:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    return tenant


@contextmanager
def _client(tenant: Tenant):
    """An authenticated Odoo client for the tenant, always closed."""
    client = tenant_service.authenticated_client(tenant)
    try:
        yield client
    finally:
        client.close()


def _normalize_filter(value: str) -> str:
    return value if value in FILTERS else "installed"


def _matches(app: odoo_apps.AppInfo, wanted: str, allowed: set[str]) -> bool:
    """Apply the selected filter to one module."""
    if wanted == "installed":
        return app.is_installed
    if wanted == "plan":
        return app.name in allowed
    if wanted == "apps":
        return app.is_app
    return True


# ---------------------------------------------------------------------------
# Index: the tenants, and what each one runs
# ---------------------------------------------------------------------------
@router.get("", response_class=HTMLResponse)
def list_view(request: Request, session: SessionDep, user: CurrentUser):
    """Every tenant, with the plan that decides which apps it may run."""
    tenants = tenant_service.list_tenants(session)
    return render(request, "apps/list.html", {"tenants": tenants})


# ---------------------------------------------------------------------------
# One tenant's apps
# ---------------------------------------------------------------------------
@router.get("/{tenant_id}", response_class=HTMLResponse)
def detail(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int,
           q: str = "", filter: str = "installed"):
    """List a tenant's apps and let an operator install or remove them."""
    tenant = _tenant_or_404(session, tenant_id)
    wanted = _normalize_filter(filter)
    apps: list[odoo_apps.AppInfo] = []
    installed: set[str] = set()
    menu_active: int | None = None
    # Named ``load_error`` and not ``error``: ``render`` fills ``error`` from the
    # query string for the redirect pattern, and this page wants to say that
    # *reading* the tenant failed, not that the last action did.
    load_error = ""

    if not tenant.provisioned:
        load_error = "This tenant has no database yet — provision it first."
    else:
        try:
            with _client(tenant) as client:
                apps = odoo_apps.list_apps(client)
                installed = {app.name for app in apps if app.is_installed}
                menu_active = odoo_apps.apps_menu_active_count(client)
        except Exception as exc:  # noqa: BLE001 - a broken tenant must still render
            load_error = f"Could not read this tenant's apps: {exc}"

    allowed = odoo_apps.allowed_by_plan(tenant.plan)
    rows = [app for app in apps if _matches(app, wanted, allowed)]
    if q.strip():
        needle = q.strip().lower()
        rows = [app for app in rows
                if needle in app.name.lower() or needle in app.label.lower()]

    return render(request, "apps/modules.html", {
        "tenant": tenant,
        "plan": tenant.plan,
        "apps": rows,
        "total": len(apps),
        "installed_count": len(installed),
        "allowed": allowed,
        "plan_app_count": len({app.name for app in apps if app.name in allowed}),
        "menu_active": menu_active,
        "guard_installed": "saas_tenant_guard" in installed,
        "q": q,
        "filter": wanted,
        "load_error": load_error,
        "can_manage": permissions.has_permission(user, permissions.PERM_APPS_MANAGE),
    })


@router.post("/{tenant_id}/{module}/install")
def install_app(request: Request, session: SessionDep, user: CurrentUser,
                tenant_id: int, module: str):
    """Install one app, if the tenant's plan allows it."""
    if error := _manage_error(user):
        return _redirect(f"/apps/{tenant_id}", error=error)
    tenant = _tenant_or_404(session, tenant_id)
    try:
        with _client(tenant) as client:
            odoo_apps.install_apps(client, tenant.plan, [module])
    except Exception as exc:  # noqa: BLE001 - reported to the operator
        _audit(request, session, user, "apps.install", tenant, module, str(exc), level="error")
        return _redirect(f"/apps/{tenant.id}", error=f"Could not install {module}: {exc}")

    _audit(request, session, user, "apps.install", tenant, module, "installed")
    return _redirect(f"/apps/{tenant.id}", flash=f"{module} installed")


@router.post("/{tenant_id}/{module}/uninstall")
def uninstall_app(request: Request, session: SessionDep, user: CurrentUser,
                  tenant_id: int, module: str):
    """Remove one app from the tenant."""
    if error := _manage_error(user):
        return _redirect(f"/apps/{tenant_id}", error=error)
    tenant = _tenant_or_404(session, tenant_id)
    try:
        with _client(tenant) as client:
            odoo_apps.uninstall_apps(client, [module])
    except Exception as exc:  # noqa: BLE001
        _audit(request, session, user, "apps.uninstall", tenant, module, str(exc), level="error")
        return _redirect(f"/apps/{tenant.id}", error=f"Could not remove {module}: {exc}")

    _audit(request, session, user, "apps.uninstall", tenant, module, "removed", level="warning")
    return _redirect(f"/apps/{tenant.id}", flash=f"{module} removed")


@router.post("/{tenant_id}/{module}/upgrade")
def upgrade_app(request: Request, session: SessionDep, user: CurrentUser,
                tenant_id: int, module: str):
    """Upgrade one app in place — the usual fix after an Odoo update."""
    if error := _manage_error(user):
        return _redirect(f"/apps/{tenant_id}", error=error)
    tenant = _tenant_or_404(session, tenant_id)
    try:
        with _client(tenant) as client:
            odoo_apps.upgrade_apps(client, [module])
    except Exception as exc:  # noqa: BLE001
        _audit(request, session, user, "apps.upgrade", tenant, module, str(exc), level="error")
        return _redirect(f"/apps/{tenant.id}", error=f"Could not upgrade {module}: {exc}")

    _audit(request, session, user, "apps.upgrade", tenant, module, "upgraded", level="warning")
    return _redirect(f"/apps/{tenant.id}", flash=f"{module} upgraded")


@router.post("/{tenant_id}/hide-menu")
def hide_menu(request: Request, session: SessionDep, user: CurrentUser,
              tenant_id: int, module: str = Form("saas_tenant_guard")):
    """Install the guard's Apps-menu hiding (needed once per tenant database)."""
    if error := _manage_error(user):
        return _redirect(f"/apps/{tenant_id}", error=error)
    tenant = _tenant_or_404(session, tenant_id)
    try:
        with _client(tenant) as client:
            hidden = odoo_apps.hide_apps_menu(client)
    except Exception as exc:  # noqa: BLE001
        _audit(request, session, user, "apps.hide_menu", tenant, module, str(exc), level="error")
        return _redirect(f"/apps/{tenant.id}", error=f"Could not hide the Apps menu: {exc}")

    if hidden is None:
        return _redirect(
            f"/apps/{tenant.id}",
            error=f"{module} is not installed in this tenant, so Odoo's Apps menu "
                  f"cannot be hidden yet — install it first.",
        )
    _audit(request, session, user, "apps.hide_menu", tenant, module, f"hidden={hidden}",
           level="warning")
    return _redirect(
        f"/apps/{tenant.id}",
        flash="Odoo's Apps menu is hidden in this tenant"
        if hidden else "Odoo's Apps menu was already hidden in this tenant",
    )


def _audit(request: Request, session, user, action: str, tenant: Tenant,
           module: str, detail: str, level: str = "info") -> None:
    """Write one app change to the audit log and commit it."""
    audit.record(session, action=action, actor=user.email, target_type="tenant",
                 target_id=tenant.id, ip=client_ip(request), level=level,
                 detail=f"{module}: {detail}")
    session.commit()
