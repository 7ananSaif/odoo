"""Manual activation and hiding of apps, per tenant.

The plan ("bouquet") says what a tenant *may* run; this module records the two
decisions a plan cannot express (see :class:`~app.models.tenant_module.TenantModule`):

``manual``
    **Manual activation.** The operator turned an app on for one tenant even
    though its plan does not list it. The install guard treats a manual app as
    authorised, so the operator does not have to edit the plan — which would
    change every other tenant on it.

``hidden``
    **Hiding.** The app stays installed (its data and URL keep working) but the
    tenant does not see it. The names are pushed into the client database as the
    ``saas.hidden_modules`` parameter, which ``saas_tenant_guard`` reads to drop
    the app's menus from the tenant's menu tree.

Reads are plain queries; writes upsert the single row per ``(tenant, module)``
and delete it again once both flags are off, so the table only ever holds live
decisions.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.tenant import Tenant
from app.models.tenant_module import TenantModule
from app.services import plan_service

_logger = logging.getLogger(__name__)


class TenantModuleError(RuntimeError):
    """Raised when a manual activation or hiding cannot be recorded."""


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def list_overrides(session: Session, tenant_id: int) -> list[TenantModule]:
    """Every override row of a tenant, alphabetically."""
    stmt = (
        select(TenantModule)
        .where(TenantModule.tenant_id == tenant_id)
        .order_by(TenantModule.technical_name)
    )
    return list(session.scalars(stmt).all())


def overrides_by_name(session: Session, tenant_id: int) -> dict[str, TenantModule]:
    """The tenant's overrides keyed by module name."""
    return {row.technical_name: row for row in list_overrides(session, tenant_id)}


def manual_names(session: Session, tenant_id: int) -> set[str]:
    """Modules activated by hand for this tenant."""
    stmt = select(TenantModule.technical_name).where(
        TenantModule.tenant_id == tenant_id, TenantModule.manual.is_(True)
    )
    return set(session.scalars(stmt).all())


def hidden_names(session: Session, tenant_id: int) -> set[str]:
    """Modules hidden from this tenant."""
    stmt = select(TenantModule.technical_name).where(
        TenantModule.tenant_id == tenant_id, TenantModule.hidden.is_(True)
    )
    return set(session.scalars(stmt).all())


def is_manual(session: Session, tenant_id: int, name: str) -> bool:
    row = _find(session, tenant_id, name)
    return bool(row and row.manual)


def is_hidden(session: Session, tenant_id: int, name: str) -> bool:
    row = _find(session, tenant_id, name)
    return bool(row and row.hidden)


def _find(session: Session, tenant_id: int, name: str) -> TenantModule | None:
    stmt = select(TenantModule).where(
        TenantModule.tenant_id == tenant_id, TenantModule.technical_name == name
    )
    return session.scalar(stmt)


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------
def effective_allowed(session: Session, tenant: Tenant, plan: Plan | None) -> set[str]:
    """Every module the tenant may install: the plan's list plus manual apps.

    The route layer uses this to decide which rows show an Install button, and
    the guard uses it to decide whether an install is legal — the two must agree.
    """
    allowed = plan_service.allowed_modules(plan)
    allowed |= manual_names(session, tenant.id)
    return allowed


def is_allowed(session: Session, tenant: Tenant, plan: Plan | None, name: str) -> bool:
    """True when ``name`` may be installed for this tenant right now."""
    if name in manual_names(session, tenant.id):
        return True
    return plan_service.plan_allows_module(plan, name)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------
def set_flags(
    session: Session,
    tenant_id: int,
    name: str,
    *,
    manual: bool | None = None,
    hidden: bool | None = None,
    note: str | None = None,
) -> TenantModule | None:
    """Turn the given flags on or off for one app; drop the row when it empties.

    ``None`` leaves a flag alone, so a caller can change one without knowing the
    other. Returns the surviving row, or ``None`` when nothing is left to store.
    """
    name = (name or "").strip()
    if not name:
        raise TenantModuleError("No app selected")

    row = _find(session, tenant_id, name)
    if row is None:
        row = TenantModule(tenant_id=tenant_id, technical_name=name, manual=False, hidden=False)
        session.add(row)

    if manual is not None:
        row.manual = manual
    if hidden is not None:
        row.hidden = hidden
    if note is not None:
        row.note = note

    if row.is_empty:
        session.delete(row)
        session.flush()
        return None
    session.flush()
    return row


def activate(session: Session, tenant_id: int, name: str) -> TenantModule:
    """Record a manual activation (idempotent)."""
    row = set_flags(session, tenant_id, name, manual=True)
    if row is None:  # pragma: no cover - manual=True can never empty the row
        raise TenantModuleError(f"Could not record {name} as manually activated")
    _logger.info("apps: %s manually activated for tenant %s", name, tenant_id)
    return row


def deactivate(session: Session, tenant_id: int, name: str) -> None:
    """Drop the manual activation flag for one app."""
    set_flags(session, tenant_id, name, manual=False)


def hide(session: Session, tenant_id: int, name: str) -> TenantModule:
    """Hide one installed app from the tenant (idempotent)."""
    row = set_flags(session, tenant_id, name, hidden=True)
    if row is None:  # pragma: no cover - hidden=True can never empty the row
        raise TenantModuleError(f"Could not hide {name}")
    _logger.info("apps: %s hidden from tenant %s", name, tenant_id)
    return row


def reveal(session: Session, tenant_id: int, name: str) -> None:
    """Show a hidden app to the tenant again."""
    set_flags(session, tenant_id, name, hidden=False)


# ---------------------------------------------------------------------------
# Propagation into the client database
# ---------------------------------------------------------------------------
def push_hidden(tenant: Tenant) -> dict[str, str]:
    """Write the tenant's hidden apps into its database and reapply the guard.

    ``tenant`` must carry a live session for the ``saas.hidden_modules``
    parameter to be read from — the caller owns that session's lifetime.
    """
    from app.db import SessionLocal  # noqa: PLC0415 (kept local: CLI scripts import this module)
    from app.services import tenant_service  # noqa: PLC0415

    with SessionLocal() as session:
        names = hidden_names(session, tenant.id)
    client = tenant_service.authenticated_client(tenant)
    try:
        from app.services import odoo_apps  # noqa: PLC0415

        payload = tenant_service.push_limits_to_database(
            tenant, hidden_modules=names, client=client
        )
        # hide_apps_menu reapplies the guard both ways: it deactivates newly
        # hidden menus and reactivates the ones that are no longer hidden.
        odoo_apps.hide_apps_menu(client)
        return payload
    finally:
        client.close()
