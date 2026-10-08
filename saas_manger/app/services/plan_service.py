"""Plans: resolve allowed modules and apply plan changes to a client database."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.tenant import Tenant

_logger = logging.getLogger(__name__)

# Modules the manager must never uninstall, whatever the plan says.
ALWAYS_KEEP = {"base", "web"}


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
    """Return the set of modules a plan allows (always includes base + web)."""
    if plan is None:
        return set(ALWAYS_KEEP)
    names = {m.technical_name for m in plan.modules if m.technical_name}
    return names | ALWAYS_KEEP


def compute_diff(installed: set[str], plan: Plan | None) -> PlanDiff:
    """Compute modules to install / uninstall to match a plan."""
    allowed = allowed_modules(plan)
    to_install = sorted(allowed - installed)
    to_uninstall = sorted((installed - allowed) - ALWAYS_KEEP)
    return PlanDiff(to_install=to_install, to_uninstall=to_uninstall)


def apply_plan(client, plan: Plan | None) -> PlanDiff:
    """Install allowed modules and uninstall the ones no longer allowed.

    ``client`` is an authenticated :class:`OdooClient`. Returns the applied diff.
    """
    installed = set(client.installed_modules())
    diff = compute_diff(installed, plan)
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
