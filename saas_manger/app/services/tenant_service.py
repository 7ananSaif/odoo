"""Tenant-facing helpers: building authenticated clients and pushing limits."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TenantStatus
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.security import decrypt_secret, encrypt_secret
from app.services import limits as limits_service
from app.services.odoo_client import OdooClient

_logger = logging.getLogger(__name__)


class TenantError(RuntimeError):
    """Raised on invalid tenant state or missing credentials."""


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def get_tenant(session: Session, tenant_id: int) -> Tenant | None:
    return session.get(Tenant, tenant_id)


def get_by_subdomain(session: Session, subdomain: str) -> Tenant | None:
    return session.scalar(select(Tenant).where(Tenant.subdomain == subdomain))


def get_by_db(session: Session, db_name: str) -> Tenant | None:
    return session.scalar(select(Tenant).where(Tenant.db_name == db_name))


def list_tenants(session: Session, status: str | None = None) -> list[Tenant]:
    stmt = select(Tenant).order_by(Tenant.name)
    if status:
        stmt = stmt.where(Tenant.status == status)
    return list(session.scalars(stmt).all())


def expiring_soon(session: Session, within_days: int = 30) -> list[Tenant]:
    """Tenants whose expiry is within ``within_days`` (and still active/trial)."""
    from datetime import timedelta  # noqa: PLC0415

    horizon = date.today() + timedelta(days=within_days)
    stmt = (
        select(Tenant)
        .where(Tenant.expiry_date.is_not(None))
        .where(Tenant.expiry_date <= horizon)
        .where(Tenant.status.in_([TenantStatus.TRIAL.value, TenantStatus.ACTIVE.value]))
        .order_by(Tenant.expiry_date)
    )
    return list(session.scalars(stmt).all())


# ---------------------------------------------------------------------------
# Credentials / clients
# ---------------------------------------------------------------------------
def store_admin_password(tenant: Tenant, password: str) -> None:
    tenant.admin_password_enc = encrypt_secret(password)


def store_api_key(tenant: Tenant, api_key: str) -> None:
    tenant.api_key_enc = encrypt_secret(api_key)


def admin_password(tenant: Tenant) -> str | None:
    return decrypt_secret(tenant.admin_password_enc)


def build_client(tenant: Tenant) -> OdooClient:
    """Build a client without authenticating (used for db-service calls)."""
    return OdooClient(db=tenant.db_name)


def authenticated_client(tenant: Tenant) -> OdooClient:
    """Return a client able to run object methods (API key preferred)."""
    client = OdooClient(db=tenant.db_name)
    api_key = decrypt_secret(tenant.api_key_enc)
    if api_key:
        client.api_key = api_key
        return client
    password = admin_password(tenant)
    if not password:
        raise TenantError(f"No stored credentials for tenant {tenant.subdomain!r}")
    client.authenticate(tenant.admin_login, password)
    return client


def open_browser_session(tenant: Tenant) -> str:
    """Authenticate and return an Odoo ``session_id`` for browser auto-login.

    Unlike :func:`authenticated_client` this always uses the stored admin
    login/password — an API key cannot produce a browser session — and returns
    the session cookie value rather than a client.
    """
    client = build_client(tenant)
    try:
        password = admin_password(tenant)
        if not password:
            raise TenantError(f"No stored admin password for tenant {tenant.subdomain!r}")
        return client.open_session(tenant.admin_login, password)
    finally:
        client.close()


# ---------------------------------------------------------------------------
# State changes
# ---------------------------------------------------------------------------
def apply_plan_limits(tenant: Tenant, plan: Plan | None) -> None:
    """Copy a plan's default limits onto the tenant (overriding them).

    Called when a tenant is created or moved to another plan; per-tenant
    overrides can then be re-applied on the tenant form.
    """
    if plan is None:
        return
    tenant.max_users = plan.max_users
    tenant.max_warehouses = plan.max_warehouses
    tenant.max_companies = plan.max_companies
    tenant.max_storage_mb = plan.max_storage_mb
    tenant.count_portal_users = plan.count_portal_users
    tenant.trial_days = plan.trial_days or tenant.trial_days


def push_limits_to_database(tenant: Tenant) -> dict[str, str]:
    """Write the tenant's ``saas.*`` parameters into its client database."""
    client = authenticated_client(tenant)
    try:
        payload = limits_service.push_limits(client, tenant)
        return payload
    finally:
        client.close()


def set_status(tenant: Tenant, status: TenantStatus) -> None:
    tenant.status = status.value
    if status == TenantStatus.CANCELLED:
        tenant.auto_renew = False


def mark_usage_checked(tenant: Tenant, when: datetime | None = None) -> None:
    tenant.last_usage_check = when or datetime.now(timezone.utc)


def push_status(tenant: Tenant) -> dict[str, str]:
    """Push only the status/expiry block (used on suspend / reactivate)."""
    client = authenticated_client(tenant)
    try:
        payload = {
            "saas.status": tenant.status,
            "saas.expiry_date": tenant.expiry_date.isoformat() if tenant.expiry_date else "",
        }
        client.push_saas_params(payload)
        return payload
    finally:
        client.close()


def push_status_suspended(tenant: Tenant) -> dict[str, str]:
    """Temporarily put the client in read-only mode (used by maintenance jobs)."""
    client = authenticated_client(tenant)
    try:
        payload = {"saas.status": TenantStatus.SUSPENDED.value}
        client.push_saas_params(payload)
        return payload
    finally:
        client.close()


def push_status_active(tenant: Tenant) -> dict[str, str]:
    """Restore the client to its real status (leave maintenance mode)."""
    client = authenticated_client(tenant)
    try:
        payload = {
            "saas.status": tenant.status,
            "saas.expiry_date": tenant.expiry_date.isoformat() if tenant.expiry_date else "",
        }
        client.push_saas_params(payload)
        return payload
    finally:
        client.close()
