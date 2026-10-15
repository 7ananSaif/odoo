"""Apps: the Odoo apps (modules) a tenant runs inside its own database.

Odoo's own Apps screen is hidden inside tenant databases by
``saas_tenant_guard``, because installing and removing apps is the provider's
decision, not the tenant's. This is where that decision is made.

Three things decide what a tenant may run, and this screen applies all three:

* its **plan** ("bouquet") — the commercial list of apps;
* a **manual activation** — an app turned on for this one tenant without
  editing the plan, which would change every other tenant on it;
* a **hide** — an installed app the tenant must not *see* (it stays installed;
  its data and URL keep working).

Nothing can be installed that no bouquet lists and that was not manually
activated: :func:`app.services.odoo_apps.assert_install_allowed` refuses it, and
the page never offers the button. Every change is written to the audit log.

The catalogue is not frozen, either. Every time this screen reads a tenant's
apps it hands them to :mod:`app.services.catalogue_service`, which records any
application the shipped catalogue did not know and adds it to the white-label
bouquet — so a module folder dropped into the addons path joins the offer on its
own. **Rescan apps** goes one step further and asks Odoo to re-read its addons
paths first, which is what makes Odoo notice a folder that is new on disk.

The Docker containers behind the stack are a different screen: see
:mod:`app.web.routes_containers`.
"""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.deps import CurrentUser, SessionDep, client_ip
from app.models.tenant import Tenant
from app.services import (
    audit,
    catalogue_service,
    limits,
    odoo_apps,
    permissions,
    tenant_modules,
    tenant_service,
)
from app.web import guards
from app.web.templating import render

router = APIRouter(prefix="/apps", tags=["apps"])

#: The filter values the module list accepts.
FILTERS = ("installed", "plan", "manual", "hidden", "apps", "all")


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


def _matches(
    app: odoo_apps.AppInfo,
    wanted: str,
    allowed: set[str],
    manual: set[str],
    hidden: set[str],
    allows_all: bool,
) -> bool:
    """Apply the selected filter to one module."""
    if wanted == "installed":
        return app.is_installed
    if wanted == "plan":
        return allows_all or app.name in allowed
    if wanted == "manual":
        return app.name in manual
    if wanted == "hidden":
        return app.name in hidden
    if wanted == "apps":
        return app.is_app
    return True


def _orphan_apps(session, apps: list[odoo_apps.AppInfo], allowed: set[str]) -> list[str]:
    """Sellable apps this tenant runs that no bouquet lists and no plan allows.

    Only real applications count. Odoo's own technical modules (``base_*``,
    ``auth_*``, …) are dependencies the server pulls in by itself; reporting
    them as "missing from every bouquet" would be noise, not a finding.
    """
    known = catalogue_service.known_names(session)
    return sorted(
        app.name for app in apps
        if app.is_app and app.is_installed
        and app.name not in known and app.name not in allowed
    )


def _push_hidden(client, tenant: Tenant, names: set[str]) -> dict[str, str]:
    """Store the hidden apps in the tenant's database and reapply the guard.

    Reapplying is what makes the change visible immediately: the guard both
    hides the newly hidden apps' menus and brings back the ones that were just
    revealed.
    """
    payload = limits.push_limits(client, tenant, hidden_modules=names)
    odoo_apps.hide_apps_menu(client)
    return payload


# ---------------------------------------------------------------------------
# Index: the tenants, and what each one runs
# ---------------------------------------------------------------------------
@router.get("", response_class=HTMLResponse)
def list_view(request: Request, session: SessionDep, user: CurrentUser):
    """Every tenant, with the plan that decides which apps it may run."""
    tenants = tenant_service.list_tenants(session)
    overrides = {
        tenant.id: len(tenant_modules.list_overrides(session, tenant.id))
        for tenant in tenants
    }
    return render(request, "apps/list.html", {
        "tenants": tenants,
        "overrides": overrides,
        "discovered_count": len(catalogue_service.discovered_names(session)),
    })


# ---------------------------------------------------------------------------
# One tenant's apps
# ---------------------------------------------------------------------------
@router.get("/{tenant_id}", response_class=HTMLResponse)
def detail(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int,
           q: str = "", filter: str = "installed"):
    """List a tenant's apps and let an operator install, activate or hide them."""
    tenant = _tenant_or_404(session, tenant_id)
    wanted = _normalize_filter(filter)
    apps: list[odoo_apps.AppInfo] = []
    installed: set[str] = set()
    menu_active: int | None = None
    just_discovered: list[str] = []
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
        if apps:
            # Anything this server offers that the catalogue did not know joins
            # it now, and is adopted into the white-label bouquet.
            just_discovered = catalogue_service.sync(session, apps, source=tenant.db_name)
            if just_discovered:
                session.commit()

    plan = tenant.plan
    allows_all = odoo_apps.plan_allows_all(plan)
    manual = tenant_modules.manual_names(session, tenant.id)
    hidden = tenant_modules.hidden_names(session, tenant.id)
    overrides = tenant_modules.overrides_by_name(session, tenant.id)
    listed = odoo_apps.allowed_by_plan(plan)
    allowed = listed | manual
    known = catalogue_service.known_names(session)

    rows = [app for app in apps if _matches(app, wanted, listed, manual, hidden, allows_all)]
    if q.strip():
        needle = q.strip().lower()
        rows = [app for app in rows
                if needle in app.name.lower() or needle in app.label.lower()]

    return render(request, "apps/modules.html", {
        "tenant": tenant,
        "plan": plan,
        "apps": rows,
        "total": len(apps),
        "installed_count": len(installed),
        "allowed": allowed,
        "listed": listed,
        "manual": manual,
        "hidden": hidden,
        "overrides": overrides,
        "plan_allows_all": allows_all,
        "catalogue_allowed": sorted(allowed),
        "plan_app_count": len({app.name for app in apps if app.name in listed}),
        "orphaned": _orphan_apps(session, apps, allowed),
        "catalogue_size": len(known),
        "discovered_count": len(catalogue_service.discovered_names(session)),
        "just_discovered": just_discovered,
        "menu_active": menu_active,
        "guard_installed": odoo_apps.GUARD_MODULE in installed,
        "q": q,
        "filter": wanted,
        "load_error": load_error,
        "can_manage": permissions.has_permission(user, permissions.PERM_APPS_MANAGE),
    })
# ---------------------------------------------------------------------------
# Install / remove / upgrade
# ---------------------------------------------------------------------------
@router.post("/{tenant_id}/{module}/install")
def install_app(request: Request, session: SessionDep, user: CurrentUser,
                tenant_id: int, module: str):
    """Install one app, if the tenant's plan — or a manual activation — allows it."""
    if error := _manage_error(user):
        return _redirect(f"/apps/{tenant_id}", error=error)
    tenant = _tenant_or_404(session, tenant_id)
    manual = tenant_modules.manual_names(session, tenant.id)
    try:
        with _client(tenant) as client:
            odoo_apps.install_apps(client, tenant.plan, [module], extra=manual)
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

    # A removed app cannot be hidden any more; the manual activation stays, so
    # the operator can put the app back without re-deciding.
    tenant_modules.reveal(session, tenant.id, module)
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


# ---------------------------------------------------------------------------
# Manual activation: an app turned on for this tenant, beyond its plan
# ---------------------------------------------------------------------------
@router.post("/{tenant_id}/{module}/activate")
def activate_app(request: Request, session: SessionDep, user: CurrentUser,
                 tenant_id: int, module: str, install: bool = Form(False)):
    """Manually activate one app for this tenant, and install it on request.

    The decision is recorded first, so it survives an install failure: the
    operator can fix the tenant and press Install again.
    """
    if error := _manage_error(user):
        return _redirect(f"/apps/{tenant_id}", error=error)
    tenant = _tenant_or_404(session, tenant_id)
    try:
        tenant_modules.activate(session, tenant.id, module)
        session.commit()
    except tenant_modules.TenantModuleError as exc:
        return _redirect(f"/apps/{tenant.id}", error=str(exc))

    _audit(request, session, user, "apps.activate", tenant, module,
           "manually activated", level="warning")

    if not install:
        return _redirect(f"/apps/{tenant.id}", flash=f"{module} activated for this tenant")

    manual = tenant_modules.manual_names(session, tenant.id)
    try:
        with _client(tenant) as client:
            odoo_apps.install_apps(client, tenant.plan, [module], extra=manual)
    except Exception as exc:  # noqa: BLE001
        return _redirect(
            f"/apps/{tenant.id}",
            error=f"{module} was activated for this tenant but could not be installed: {exc}",
        )
    _audit(request, session, user, "apps.install", tenant, module, "installed (manual)")
    return _redirect(f"/apps/{tenant.id}", flash=f"{module} activated and installed")


@router.post("/{tenant_id}/{module}/deactivate")
def deactivate_app(request: Request, session: SessionDep, user: CurrentUser,
                   tenant_id: int, module: str):
    """Drop the manual activation: the app follows the plan again."""
    if error := _manage_error(user):
        return _redirect(f"/apps/{tenant_id}", error=error)
    tenant = _tenant_or_404(session, tenant_id)
    tenant_modules.deactivate(session, tenant.id, module)
    _audit(request, session, user, "apps.deactivate", tenant, module,
           "manual activation removed", level="warning")
    return _redirect(
        f"/apps/{tenant.id}",
        flash=f"{module} follows the plan again (it is still installed)",
    )


# ---------------------------------------------------------------------------
# Hiding: installed, but the tenant must not see it
# ---------------------------------------------------------------------------
@router.post("/{tenant_id}/{module}/hide")
def hide_app(request: Request, session: SessionDep, user: CurrentUser,
             tenant_id: int, module: str):
    """Hide one installed app from the tenant without uninstalling it."""
    if error := _manage_error(user):
        return _redirect(f"/apps/{tenant_id}", error=error)
    tenant = _tenant_or_404(session, tenant_id)

    if module in odoo_apps.PROTECTED:
        return _redirect(f"/apps/{tenant.id}", error=f"{module} cannot be hidden")

    try:
        with _client(tenant) as client:
            if module not in set(client.installed_modules()):
                return _redirect(f"/apps/{tenant.id}",
                                 error=f"{module} is not installed in this tenant")
            tenant_modules.hide(session, tenant.id, module)
            session.commit()
            names = tenant_modules.hidden_names(session, tenant.id)
            _push_hidden(client, tenant, names)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        _audit(request, session, user, "apps.hide", tenant, module, str(exc), level="error")
        return _redirect(f"/apps/{tenant.id}", error=f"Could not hide {module}: {exc}")

    _audit(request, session, user, "apps.hide", tenant, module, "hidden", level="warning")
    return _redirect(f"/apps/{tenant.id}", flash=f"{module} is now hidden from {tenant.name}")


@router.post("/{tenant_id}/{module}/unhide")
def unhide_app(request: Request, session: SessionDep, user: CurrentUser,
               tenant_id: int, module: str):
    """Show a hidden app to the tenant again."""
    if error := _manage_error(user):
        return _redirect(f"/apps/{tenant_id}", error=error)
    tenant = _tenant_or_404(session, tenant_id)
    try:
        with _client(tenant) as client:
            tenant_modules.reveal(session, tenant.id, module)
            session.commit()
            names = tenant_modules.hidden_names(session, tenant.id)
            _push_hidden(client, tenant, names)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        _audit(request, session, user, "apps.unhide", tenant, module, str(exc), level="error")
        return _redirect(f"/apps/{tenant.id}", error=f"Could not show {module}: {exc}")

    _audit(request, session, user, "apps.unhide", tenant, module, "visible again")
    return _redirect(f"/apps/{tenant.id}", flash=f"{module} is visible to the tenant again")


# ---------------------------------------------------------------------------
# Keeping every app inside a bouquet
# ---------------------------------------------------------------------------
@router.post("/{tenant_id}/{module}/add-to-bouquet")
def add_to_bouquet(request: Request, session: SessionDep, user: CurrentUser,
                   tenant_id: int, module: str):
    """Record an app the tenant runs in the white-label bouquet.

    Discovery normally does this on its own; this is the manual door for the
    case where the white-label bouquet was created after the app was seen.
    """
    if error := _manage_error(user):
        return _redirect(f"/apps/{tenant_id}", error=error)
    tenant = _tenant_or_404(session, tenant_id)

    plan = catalogue_service.adopt(session, [module])
    if plan is None:
        return _redirect(
            f"/apps/{tenant.id}",
            error="No white-label bouquet exists — mark a plan as white-label first.",
        )
    if module in {m.technical_name for m in plan.modules}:
        return _redirect(f"/apps/{tenant.id}",
                         flash=f"{module} is already in {plan.name}")

    session.commit()
    _audit(request, session, user, "apps.add_to_bouquet", tenant, module, f"added to {plan.code}",
           level="warning")
    return _redirect(f"/apps/{tenant.id}", flash=f"{module} added to the {plan.name} bouquet")


@router.post("/{tenant_id}/rescan")
def rescan_apps(request: Request, session: SessionDep, user: CurrentUser, tenant_id: int):
    """Re-read the tenant's addons paths, then sync the catalogue.

    Dropping a module folder on disk is not enough for Odoo to know about it:
    the module list has to be updated. This is that step, followed by discovery,
    so an app added to the server becomes installable without touching code.
    """
    if error := _manage_error(user):
        return _redirect(f"/apps/{tenant_id}", error=error)
    tenant = _tenant_or_404(session, tenant_id)
    try:
        with _client(tenant) as client:
            count = odoo_apps.refresh_module_list(client)
            apps = odoo_apps.list_apps(client)
    except Exception as exc:  # noqa: BLE001
        _audit(request, session, user, "apps.rescan", tenant, "*", str(exc), level="error")
        return _redirect(f"/apps/{tenant.id}", error=f"Could not rescan this tenant: {exc}")

    added = catalogue_service.sync(session, apps, source=tenant.db_name)
    _audit(request, session, user, "apps.rescan", tenant, "*",
           f"modules={count} discovered={sorted(added)}", level="warning")
    flash = f"Rescanned this tenant: {count} modules"
    if added:
        flash += f" · discovered {', '.join(sorted(added))} and added to a bouquet"
    return _redirect(f"/apps/{tenant.id}", flash=flash)


# ---------------------------------------------------------------------------
# The tenant's own Apps menu
# ---------------------------------------------------------------------------
@router.post("/{tenant_id}/hide-menu")
def hide_menu(request: Request, session: SessionDep, user: CurrentUser,
              tenant_id: int, module: str = Form(odoo_apps.GUARD_MODULE)):
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
