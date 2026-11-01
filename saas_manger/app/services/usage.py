"""Refresh per-tenant usage counters and raise limit alerts."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.services import audit, pg_tools, tenant_service
from app.services.odoo_client import OdooError

_logger = logging.getLogger(__name__)

ALERT_THRESHOLD = 80  # percent


@dataclass
class UsageSnapshot:
    """Counters read from a client database."""

    users: int = 0
    warehouses: int = 0
    companies: int = 0
    storage_mb: float = 0.0
    db_size_mb: float = 0.0
    last_login: datetime | None = None
    warnings: list[str] = field(default_factory=list)


def read_usage(tenant: Tenant) -> UsageSnapshot:
    """Query the client database for the current counters."""
    snapshot = UsageSnapshot()
    try:
        client = tenant_service.authenticated_client(tenant)
    except Exception as exc:  # noqa: BLE001 - no credentials / offline
        snapshot.warnings.append(f"client unavailable: {exc}")
        return snapshot
    try:
        users = client.call_kw(
            "res.users", "search_count",
            [[("active", "=", True), ("share", "=", False)]],
        )
        companies = client.call_kw("res.company", "search_count", [[("active", "=", True)]])
        warehouses = 0
        try:
            warehouses = client.call_kw("stock.warehouse", "search_count", [[("active", "=", True)]])
        except OdooError:
            warehouses = 0
        snapshot.users = int(users or 0)
        snapshot.companies = int(companies or 0)
        snapshot.warehouses = int(warehouses or 0)
    except OdooError as exc:
        snapshot.warnings.append(f"usage query failed: {exc}")
    finally:
        client.close()

    try:
        snapshot.db_size_mb = pg_tools.db_size_mb(tenant.db_name)
    except pg_tools.PgError as exc:
        snapshot.warnings.append(f"db size failed: {exc}")
    return snapshot


def refresh_tenant(session: Session, tenant: Tenant) -> list[str]:
    """Update a tenant's usage fields and return any limit warnings."""
    snapshot = read_usage(tenant)
    tenant.current_users = snapshot.users
    tenant.current_warehouses = snapshot.warehouses
    tenant.current_companies = snapshot.companies
    tenant.current_db_size_mb = snapshot.db_size_mb
    tenant.last_usage_check = datetime.now(timezone.utc)

    warnings = list(snapshot.warnings)
    warnings += alert_messages(tenant)
    for message in warnings:
        audit.record(
            session,
            action="usage.alert" if message in alert_messages(tenant) else "usage.warning",
            target_type="tenant",
            target_id=tenant.id,
            level="warning",
            detail=message,
        )
    return warnings


def alert_messages(tenant: Tenant) -> list[str]:
    """Return 80% / 100% alerts for this tenant."""
    messages: list[str] = []
    for key, label in (
        ("users", "users"),
        ("warehouses", "warehouses"),
        ("companies", "companies"),
        ("storage", "storage"),
        ("db_size", "database size"),
    ):
        percent = tenant.usage_percent(key)
        if percent >= 100:
            messages.append(f"{tenant.subdomain}: {label} at {percent}% of the plan limit")
        elif percent >= ALERT_THRESHOLD:
            messages.append(f"{tenant.subdomain}: {label} at {percent}% of the plan limit")
    return messages


def refresh_all(session: Session) -> dict[str, list[str]]:
    """Refresh every tenant; return {subdomain: warnings}."""
    results: dict[str, list[str]] = {}
    for tenant in tenant_service.list_tenants(session):
        results[tenant.subdomain] = refresh_tenant(session, tenant)
    return results
