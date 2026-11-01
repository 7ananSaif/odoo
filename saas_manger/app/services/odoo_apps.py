"""Odoo apps (modules) of a tenant, driven from the manager.

The provider decides which apps a tenant runs. Tenants cannot do it themselves
because ``saas_tenant_guard`` hides Odoo's own Apps menu inside their database;
this module is the manager's half of that contract. It reads
``ir.module.module`` over RPC and installs / removes / upgrades modules on the
tenant's behalf, always within what the tenant's plan authorises.

Every call goes through :class:`~app.services.odoo_client.OdooClient`, which
carries the manager token as a header *and* inside the RPC context, so the core
``# SAAS-PATCH`` guard (see ``saas_manger/patch``) accepts it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.models.plan import Plan
from app.services import plan_service
from app.services.odoo_client import OdooError

_logger = logging.getLogger(__name__)

#: Modules the manager never removes, whatever the operator asks for.
PROTECTED = frozenset({"base", "web"})

#: The tenant-side module that hides Odoo's own Apps menu, and the model method
#: it exposes for that. The method name deliberately has no leading underscore:
#: Odoo refuses remote calls to private methods.
GUARD_MODULE = "saas_tenant_guard"
GUARD_HIDE_METHOD = "saas_guard_hide_apps_menus"

#: Fields read from ``ir.module.module``. Every one of them has existed for many
#: major versions, so a field that a future Odoo renames is the only thing that
#: could break this list — and the page would say so rather than fail silently.
_MODULE_FIELDS = [
    "name",
    "shortdesc",
    "summary",
    "state",
    "category_id",
    "application",
    "installed_version",
    "latest_version",
    "author",
]

#: States that mean "this module is part of the database right now".
INSTALLED_STATES = ("installed", "to upgrade", "to remove")

_STATE_LABELS = {
    "installed": "installed",
    "uninstalled": "not installed",
    "to install": "queued to install",
    "to upgrade": "queued to upgrade",
    "to remove": "queued to remove",
    "uninstallable": "uninstallable",
}


class AppError(RuntimeError):
    """Raised when an app change is refused here, or Odoo rejects it."""


@dataclass(frozen=True)
class AppInfo:
    """One Odoo module, as shown on the manager's Apps screen."""

    name: str
    label: str
    summary: str
    category: str
    state: str
    installed_version: str
    latest_version: str
    is_app: bool
    author: str

    @property
    def is_installed(self) -> bool:
        """True when the module is present in the database."""
        return self.state in INSTALLED_STATES

    @property
    def state_label(self) -> str:
        """Human wording for the module state."""
        return _STATE_LABELS.get(self.state, self.state)

    @property
    def can_uninstall(self) -> bool:
        """True when the operator is allowed to remove this module."""
        return self.is_installed and self.name not in PROTECTED


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def _to_app(row: dict) -> AppInfo:
    category = row.get("category_id")
    return AppInfo(
        name=row.get("name") or "",
        label=row.get("shortdesc") or row.get("name") or "",
        summary=(row.get("summary") or "").strip(),
        category=category[1] if isinstance(category, (list, tuple)) and len(category) > 1 else "",
        state=row.get("state") or "unknown",
        installed_version=row.get("installed_version") or "",
        latest_version=row.get("latest_version") or "",
        is_app=bool(row.get("application")),
        author=row.get("author") or "",
    )


def list_apps(client, *, applications_only: bool = False) -> list[AppInfo]:
    """Every module in the tenant's database: apps first, then alphabetically."""
    domain = [("application", "=", True)] if applications_only else []
    rows = client.call_kw("ir.module.module", "search_read", [domain, _MODULE_FIELDS])
    apps = [_to_app(row) for row in rows or []]
    apps.sort(key=lambda app: (not app.is_app, app.label.lower()))
    return apps


def refresh_module_list(client) -> int:
    """Ask Odoo to rescan its addons paths, so a newly added folder shows up.

    Odoo only learns about a module folder dropped on disk when its module list
    is updated. Returns how many modules exist afterwards, so the caller can
    report the effect.
    """
    client.call_kw("ir.module.module", "update_list", [])
    return len(list_apps(client))


def installed_count(client) -> int:
    """How many apps the tenant currently has installed."""
    try:
        return len(client.installed_modules())
    except Exception as exc:  # noqa: BLE001 - a broken tenant must not break the list
        _logger.info("apps: cannot count installed modules: %s", exc)
        return 0


def apps_menu_active_count(client) -> int | None:
    """How many module-installer menus tenant users can still see.

    ``None`` means the question could not be answered (typically the manager
    token was refused), ``0`` means the Apps menu is hidden as it should be.
    """
    try:
        actions = client.call_kw(
            "ir.actions.act_window", "search",
            [[("res_model", "=", "ir.module.module")]],
        )
        if not actions:
            return 0
        references = [f"ir.actions.act_window,{action_id}" for action_id in actions]
        return int(client.call_kw("ir.ui.menu", "search_count", [[("action", "in", references)]]) or 0)
    except Exception as exc:  # noqa: BLE001
        _logger.info("apps: cannot read the Apps menu state: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Plan gating
# ---------------------------------------------------------------------------
def allowed_by_plan(plan: Plan | None) -> set[str]:
    """The technical names the tenant's plan lists (always base + web).

    This is the plan's declared content. A white-label plan also authorises
    everything else — installing is checked against :func:`plan_allows`, not
    against this set.
    """
    return plan_service.allowed_modules(plan)


def plan_allows_all(plan: Plan | None) -> bool:
    """True when the plan is white-label: every app in the database is allowed."""
    return plan_service.allows_all(plan)


def plan_allows(plan: Plan | None, name: str, *, extra: set[str] | None = None) -> bool:
    """True when installing ``name`` is authorised for this plan.

    ``extra`` carries the tenant's manually activated apps — turned on for one
    tenant without touching the plan (see :mod:`app.services.tenant_modules`).
    """
    return plan_service.plan_allows_module(plan, name, extra=extra)


def assert_install_allowed(
    plan: Plan | None,
    names: list[str],
    *,
    extra: set[str] | None = None,
) -> None:
    """Refuse modules neither the tenant's plan nor a manual activation allows.

    Dependencies of an allowed module are pulled in by Odoo itself, so the check
    only looks at what the operator explicitly asked for. Nothing bypasses it:
    an app that no bouquet lists stays uninstallable until it is added to a plan
    or activated manually for this tenant.
    """
    refused = sorted({name for name in names if not plan_allows(plan, name, extra=extra)})
    if refused:
        plan_name = plan.name if plan else "the tenant's plan"
        raise AppError(
            f"{', '.join(refused)} is not part of {plan_name}. Add it to the plan, "
            f"activate it for this tenant, or move the tenant to a plan that "
            f"includes it."
        )


def assert_uninstall_allowed(names: list[str]) -> None:
    """Refuse removing the modules the manager itself depends on."""
    refused = sorted(set(names) & PROTECTED)
    if refused:
        raise AppError(f"{', '.join(refused)} cannot be removed — the manager needs it.")


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------
def install_apps(
    client,
    plan: Plan | None,
    names: list[str],
    *,
    extra: set[str] | None = None,
) -> list[str]:
    """Install ``names`` for a tenant, checking the plan (and manual apps) first.

    ``extra`` is the tenant's set of manually activated apps, which are allowed
    even though the plan does not list them.
    """
    names = _clean(names)
    assert_install_allowed(plan, names, extra=extra)
    _logger.info("apps: installing %s", names)
    client.install_modules(names)
    hide_apps_menu(client)
    return names


def uninstall_apps(client, names: list[str]) -> list[str]:
    """Remove ``names`` from a tenant."""
    names = _clean(names)
    assert_uninstall_allowed(names)
    _logger.info("apps: uninstalling %s", names)
    client.uninstall_modules(names)
    hide_apps_menu(client)
    return names


def upgrade_apps(client, names: list[str]) -> list[str]:
    """Upgrade ``names`` in place (the fix for a module stuck after an update)."""
    names = _clean(names)
    installed = set(client.installed_modules())
    missing = sorted(set(names) - installed)
    if missing:
        raise AppError(f"{', '.join(missing)} is not installed")
    _logger.info("apps: upgrading %s", names)
    _upgrade_now(client, names)
    hide_apps_menu(client)
    return names


def _upgrade_now(client, names: list[str]) -> None:
    """Ask Odoo to upgrade the given modules, without touching the Apps menu.

    Kept separate from :func:`upgrade_apps` so :func:`hide_apps_menu` can bring
    an outdated guard up to date without recursing back into itself.
    """
    ids = client.call_kw("ir.module.module", "search", [[("name", "in", names)]])
    if ids:
        client.call_kw("ir.module.module", "button_immediate_upgrade", [ids])


def _clean(names: list[str]) -> list[str]:
    """De-duplicate the module names, keeping the order, refusing an empty set."""
    wanted: list[str] = []
    for name in names:
        cleaned = (name or "").strip()
        if cleaned and cleaned not in wanted:
            wanted.append(cleaned)
    if not wanted:
        raise AppError("No app selected")
    return wanted


def hide_apps_menu(client) -> int | None:
    """Ask the tenant's guard to hide Odoo's Apps menu.

    Returns how many menus were hidden, or ``None`` when the tenant has no
    ``saas_tenant_guard`` installed — an unguarded tenant keeps its own Apps
    menu, and that must never fail the app change that just succeeded.

    A tenant may still carry an *older* guard that does not expose the method:
    it is upgraded once and the call retried, so the operator never has to know
    which version their databases run.
    """
    if GUARD_MODULE not in set(client.installed_modules()):
        _logger.info("apps: %s is not installed here, Apps menu left alone", GUARD_MODULE)
        return None

    try:
        return _call_hide(client)
    except OdooError as exc:
        if GUARD_HIDE_METHOD not in str(exc):
            raise
        _logger.info("apps: upgrading %s so it can hide the Apps menu", GUARD_MODULE)
        _upgrade_now(client, [GUARD_MODULE])
        return _call_hide(client)


def _call_hide(client) -> int:
    """Call the guard's hide method and return how many menus it hid."""
    hidden = client.call_kw("ir.ui.menu", GUARD_HIDE_METHOD, [])
    _logger.info("apps: guard hid %s menu(s)", hidden)
    return int(hidden or 0)
