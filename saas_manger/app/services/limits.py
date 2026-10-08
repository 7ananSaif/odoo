"""Push tenant limits / status into the client database as ``saas.*`` parameters.

The core patch reads these keys (``ir.config_parameter``) to enforce the plan
inside the client database and to switch it read-only when suspended/expired.
Only the manager (which sends the token) can write them.
"""
from __future__ import annotations

from datetime import date

from app.models.enums import TenantStatus
from app.models.tenant import Tenant

# Mapping: tenant attribute -> ir.config_parameter key understood by saas_lock.py
LIMIT_PARAM_MAP: dict[str, str] = {
    "max_users": "saas.max_users",
    "max_warehouses": "saas.max_warehouses",
    "max_companies": "saas.max_companies",
    "max_storage_mb": "saas.max_storage_mb",
    "max_db_size_mb": "saas.max_db_size_mb",
}


def build_param_payload(tenant: Tenant) -> dict[str, str]:
    """Return the complete ``saas.*`` payload for a tenant."""
    payload: dict[str, str] = {
        "saas.status": tenant.status,
        "saas.tenant_id": str(tenant.id),
        "saas.expiry_date": tenant.expiry_date.isoformat() if tenant.expiry_date else "",
        "saas.trial_days": str(tenant.trial_days),
        "saas.plan": tenant.plan.name if tenant.plan else "",
        "saas.block_writes": "1" if tenant.block_writes else "0",
        "saas.count_portal_users": "1" if tenant.count_portal_users else "0",
    }
    for attribute, key in LIMIT_PARAM_MAP.items():
        value = getattr(tenant, attribute, 0) or 0
        payload[key] = str(value)
    return payload


def push_limits(client, tenant: Tenant) -> dict[str, str]:
    """Write every ``saas.*`` parameter of ``tenant`` into its client DB.

    ``client`` is an authenticated :class:`~app.services.odoo_client.OdooClient`.
    Returns the payload that was pushed.
    """
    from app.services import settings_service  # noqa: PLC0415 (avoid cycle at import time)

    payload = build_param_payload(tenant)
    # 'suspended'/'expired' also honours the global block_writes default.
    client.push_saas_params(payload)
    return payload


def status_to_client(status: str) -> str:
    """Normalise a TenantStatus value for pushing to the client."""
    try:
        return TenantStatus(status).value
    except ValueError:
        return TenantStatus.ACTIVE.value


def dumps(payload: dict[str, str]) -> str:
    """Render a payload for audit detail (stable ordering)."""
    return ", ".join(f"{k}={v}" for k, v in sorted(payload.items()))


def is_expired(tenant: Tenant, today: date | None = None) -> bool:
    """Return True when the tenant has an expiry date in the past."""
    if not tenant.expiry_date:
        return False
    return tenant.expiry_date < (today or date.today())
