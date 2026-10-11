"""Plan module diffing, downgrade protection and the saas.* limit payload."""
from __future__ import annotations

import pytest

from app.models.plan import Plan, PlanModule
from app.models.tenant import Tenant
from app.services import limits as limits_service
from app.services import plan_service


def make_plan(**kwargs) -> Plan:
    plan = Plan(name="Standard", code="standard")
    for key, value in kwargs.items():
        setattr(plan, key, value)
    return plan


def test_compute_diff_installs_missing_and_keeps_base():
    plan = make_plan()
    plan.modules = [PlanModule(technical_name="stock"), PlanModule(technical_name="sale_management")]
    diff = plan_service.compute_diff(installed={"base", "web"}, plan=plan)
    assert set(diff.to_install) == {"stock", "sale_management"}
    assert diff.to_uninstall == []


def test_compute_diff_uninstalls_disallowed_but_never_base_or_web():
    plan = make_plan()
    plan.modules = [PlanModule(technical_name="stock")]
    diff = plan_service.compute_diff(
        installed={"base", "web", "stock", "mrp", "account"}, plan=plan,
    )
    assert diff.to_install == []
    assert set(diff.to_uninstall) == {"mrp", "account"}
    assert "base" not in diff.to_uninstall
    assert "web" not in diff.to_uninstall


def test_allowed_modules_always_contains_base_and_web():
    assert plan_service.allowed_modules(None) == {"base", "web"}


def test_downgrade_blocked_when_usage_exceeds_new_limit():
    tenant = Tenant(name="Acme", subdomain="acme", db_name="acme", current_users=8, max_users=10)
    problems = plan_service.check_downgrade(tenant, {"max_users": 5})
    assert problems, "expected a downgrade problem"
    assert "users" in problems[0]


def test_downgrade_allowed_when_usage_fits():
    tenant = Tenant(name="Acme", subdomain="acme", db_name="acme", current_users=3)
    assert plan_service.check_downgrade(tenant, {"max_users": 5}) == []
    plan_service.assert_downgrade_allowed(tenant, {"max_users": 5})


def test_downgrade_raises_with_reduction_hint():
    tenant = Tenant(name="Acme", subdomain="acme", db_name="acme", current_warehouses=4)
    with pytest.raises(plan_service.PlanError) as exc:
        plan_service.assert_downgrade_allowed(tenant, {"max_warehouses": 2})
    assert "reduce by 2" in str(exc.value)


def test_zero_limit_means_unlimited():
    tenant = Tenant(name="Acme", subdomain="acme", db_name="acme", current_users=99)
    assert plan_service.check_downgrade(tenant, {"max_users": 0}) == []


def test_build_param_payload_maps_limits_and_status():
    tenant = Tenant(
        name="Acme", subdomain="acme", db_name="acme",
        status="active", max_users=7, max_warehouses=2, max_companies=3,
        max_storage_mb=1024, max_db_size_mb=2048,
    )
    tenant.id = 42
    payload = limits_service.build_param_payload(tenant)
    assert payload["saas.max_users"] == "7"
    assert payload["saas.max_warehouses"] == "2"
    assert payload["saas.max_companies"] == "3"
    assert payload["saas.max_storage_mb"] == "1024"
    assert payload["saas.max_db_size_mb"] == "2048"
    assert payload["saas.status"] == "active"
    assert payload["saas.tenant_id"] == "42"


def test_is_expired():
    from datetime import date, timedelta  # noqa: PLC0415

    tenant = Tenant(name="Acme", subdomain="acme", db_name="acme", expiry_date=date.today() - timedelta(days=1))
    assert limits_service.is_expired(tenant) is True
    tenant.expiry_date = date.today() + timedelta(days=1)
    assert limits_service.is_expired(tenant) is False
