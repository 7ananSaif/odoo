"""Plans: resolve allowed modules and apply plan changes to a client database."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.tenant import Tenant
from app.services.app_catalogue import ALWAYS_KEEP

_logger = logging.getLogger(__name__)


class PlanError(RuntimeError):
    """Raised when a plan change cannot be applied."""


@dataclass
class PlanDiff:
    """The module changes required to move a tenant onto a plan."""

    to_install: list[str]
    to_uninstall: list[str]


def get_plan(session: Session, plan_id: int) -> Plan | None:
    return session.get(Plan, plan_id)


def list_plans(session: Session, active_only: bool = False) -> list[Plan]:
    stmt = select(Plan).order_by(Plan.name)
    if active_only:
        stmt = stmt.where(Plan.active.is_(True))
    return list(session.scalars(stmt).all())


def allowed_modules(plan: Plan | None) -> set[str]:
    """Return the set of modules a plan lists explicitly (always base + web).

    This is the plan's *declared* content, which is what a plan change installs
    and what the app screens show as "in the plan". A white-label plan also
    authorises everything else — see :func:`allows_all`.
    """
    if plan is None:
        return set(ALWAYS_KEEP)
    names = {m.technical_name for m in plan.modules if m.technical_name}
    return names | ALWAYS_KEEP


def allows_all(plan: Plan | None) -> bool:
    """True when the plan is white-label: it authorises every app, not just its list."""
    return bool(plan is not None and plan.all_apps)


def plan_allows_module(plan: Plan | None, name: str, *, extra: set[str] | None = None) -> bool:
    """True when ``plan`` authorises installing ``name``.

    ``extra`` carries per-tenant exceptions (manually activated apps), so the
    caller can ask the same question the manager will act on.
    """
    if not name:
        return False
    if name in ALWAYS_KEEP:
        return True
    if extra and name in extra:
        return True
    if allows_all(plan):
        return True
    return name in allowed_modules(plan)


def compute_diff(installed: set[str], plan: Plan | None) -> PlanDiff:
    """Compute modules to install / uninstall to match a plan.

    A white-label plan installs what it lists and removes **nothing**: it
    authorises every app, so no installed app can be "not allowed by it".
    """
    allowed = allowed_modules(plan)
    to_install = sorted(allowed - installed)
    if allows_all(plan):
        return PlanDiff(to_install=to_install, to_uninstall=[])
    to_uninstall = sorted((installed - allowed) - ALWAYS_KEEP)
    return PlanDiff(to_install=to_install, to_uninstall=to_uninstall)


def apply_plan(client, plan: Plan | None, *, keep: set[str] | None = None) -> PlanDiff:
    """Install allowed modules and uninstall the ones no longer allowed.

    ``client`` is an authenticated :class:`OdooClient`. ``keep`` names modules
    that must survive the change even though the plan does not list them — the
    apps an operator activated by hand for this tenant, which a plan change must
    not silently undo. Returns the applied diff.
    """
    installed = set(client.installed_modules())
    diff = compute_diff(installed, plan)
    if keep:
        diff.to_uninstall = [name for name in diff.to_uninstall if name not in keep]
    if diff.to_install:
        _logger.info("plan: installing %s", diff.to_install)
        client.install_modules(diff.to_install)
    if diff.to_uninstall:
        _logger.info("plan: uninstalling %s", diff.to_uninstall)
        client.uninstall_modules(diff.to_uninstall)
    return diff


# ---------------------------------------------------------------------------
# Downgrade protection
# ---------------------------------------------------------------------------
LIMIT_LABELS = {
    "max_users": "users",
    "max_warehouses": "warehouses",
    "max_companies": "companies",
    "max_storage_mb": "storage (MB)",
    "max_db_size_mb": "database size (MB)",
}

USAGE_ATTRS = {
    "max_users": "current_users",
    "max_warehouses": "current_warehouses",
    "max_companies": "current_companies",
    "max_storage_mb": "current_storage_mb",
    "max_db_size_mb": "current_db_size_mb",
}


def check_downgrade(tenant: Tenant, new_limits: dict[str, int]) -> list[str]:
    """Return the list of violations when ``new_limits`` are below current usage.

    An empty list means the downgrade is allowed. ``0`` means "unlimited".
    """
    problems: list[str] = []
    for key, limit in new_limits.items():
        if not limit:
            continue
        usage = float(getattr(tenant, USAGE_ATTRS.get(key, ""), 0) or 0)
        if usage > limit:
            problems.append(
                f"{LIMIT_LABELS.get(key, key)}: used {usage:g}, new limit {limit} "
                f"(reduce by {usage - limit:g})"
            )
    return problems


def assert_downgrade_allowed(tenant: Tenant, new_limits: dict[str, int]) -> None:
    """Raise PlanError listing everything that must be reduced first."""
    problems = check_downgrade(tenant, new_limits)
    if problems:
        raise PlanError(
            "Downgrade blocked — the current usage exceeds the new limits:\n- "
            + "\n- ".join(problems)
        )
