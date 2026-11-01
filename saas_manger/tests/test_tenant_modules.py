"""Manual activation and hiding of apps, per tenant.

The plan decides what a tenant may install; these tests cover the two decisions
a plan cannot express — an app turned on for one tenant only, and an app the
tenant must not see — and the fact that the install guard honours the first.
"""
from __future__ import annotations

import pytest

from app.models.plan import Plan, PlanModule
from app.models.tenant import Tenant
from app.services import odoo_apps, plan_service, tenant_modules


@pytest.fixture()
def tenant(session):
    plan = Plan(name="Starter", code="starter-test", all_apps=False)
    plan.modules = [PlanModule(technical_name="sale_management")]
    session.add(plan)
    session.flush()
    row = Tenant(
        name="Acme", subdomain="acme-test", db_name="acme_test",
        plan_id=plan.id, provisioned=True,
    )
    session.add(row)
    session.flush()
    return row


# ---------------------------------------------------------------------------
# Manual activation
# ---------------------------------------------------------------------------
def test_activate_records_one_row(session, tenant):
    assert tenant_modules.manual_names(session, tenant.id) == set()
    tenant_modules.activate(session, tenant.id, "hotel")
    assert tenant_modules.manual_names(session, tenant.id) == {"hotel"}


def test_activate_is_idempotent(session, tenant):
    tenant_modules.activate(session, tenant.id, "hotel")
    tenant_modules.activate(session, tenant.id, "hotel")
    assert len(tenant_modules.list_overrides(session, tenant.id)) == 1


def test_deactivate_removes_the_row_when_nothing_else_is_set(session, tenant):
    tenant_modules.activate(session, tenant.id, "hotel")
    tenant_modules.deactivate(session, tenant.id, "hotel")
    assert tenant_modules.manual_names(session, tenant.id) == set()
    assert tenant_modules.list_overrides(session, tenant.id) == []


def test_empty_name_is_refused(session, tenant):
    with pytest.raises(tenant_modules.TenantModuleError):
        tenant_modules.activate(session, tenant.id, "  ")


def test_effective_allowed_adds_manual_apps_to_the_plan(session, tenant):
    tenant_modules.activate(session, tenant.id, "hotel")
    allowed = tenant_modules.effective_allowed(session, tenant, tenant.plan)
    assert "sale_management" in allowed  # from the plan
    assert "hotel" in allowed            # manual
    assert "library" not in allowed      # neither


def test_is_allowed_matches_the_install_guard(session, tenant):
    """The page's answer and the guard's answer must be the same one."""
    assert tenant_modules.is_allowed(session, tenant, tenant.plan, "hotel") is False
    tenant_modules.activate(session, tenant.id, "hotel")
    assert tenant_modules.is_allowed(session, tenant, tenant.plan, "hotel") is True

    manual = tenant_modules.manual_names(session, tenant.id)
    # The guard accepts it because of the manual activation...
    odoo_apps.assert_install_allowed(tenant.plan, ["hotel"], extra=manual)


def test_guard_refuses_an_app_neither_in_the_plan_nor_manual(session, tenant):
    with pytest.raises(odoo_apps.AppError) as excinfo:
        odoo_apps.assert_install_allowed(tenant.plan, ["library"], extra=set())
    assert "library" in str(excinfo.value)


def test_white_label_plan_needs_no_activation(session, tenant):
    tenant.plan.all_apps = True
    assert tenant_modules.is_allowed(session, tenant, tenant.plan, "library") is True


# ---------------------------------------------------------------------------
# Hiding
# ---------------------------------------------------------------------------
def test_hide_and_reveal(session, tenant):
    tenant_modules.hide(session, tenant.id, "sale_management")
    assert tenant_modules.hidden_names(session, tenant.id) == {"sale_management"}

    tenant_modules.reveal(session, tenant.id, "sale_management")
    assert tenant_modules.hidden_names(session, tenant.id) == set()
    assert tenant_modules.list_overrides(session, tenant.id) == []


def test_a_row_carries_both_decisions(session, tenant):
    tenant_modules.activate(session, tenant.id, "hotel")
    tenant_modules.hide(session, tenant.id, "hotel")
    assert tenant_modules.is_manual(session, tenant.id, "hotel") is True
    assert tenant_modules.is_hidden(session, tenant.id, "hotel") is True

    # Clearing one leaves the other in place rather than dropping the row.
    tenant_modules.reveal(session, tenant.id, "hotel")
    assert tenant_modules.is_manual(session, tenant.id, "hotel") is True
    assert tenant_modules.is_hidden(session, tenant.id, "hotel") is False


def test_overrides_by_name_indexes_the_rows(session, tenant):
    tenant_modules.activate(session, tenant.id, "hotel")
    tenant_modules.hide(session, tenant.id, "library")
    index = tenant_modules.overrides_by_name(session, tenant.id)
    assert set(index) == {"hotel", "library"}
    assert index["hotel"].manual is True
    assert index["library"].hidden is True


# ---------------------------------------------------------------------------
# The payload pushed into the tenant's database
# ---------------------------------------------------------------------------
def test_hidden_modules_parameter_is_rendered_sorted_and_deduplicated():
    from app.services import limits

    value = limits.hidden_modules_value({"hotel", "hotel", "library", ""})
    assert value == "hotel,library"


def test_payload_omits_the_parameter_when_not_given(session, tenant):
    """A plain "push limits" must not un-hide an app the operator hid."""
    from app.services import limits

    payload = limits.build_param_payload(tenant)
    assert limits.HIDDEN_MODULES_PARAM not in payload


def test_payload_includes_the_parameter_when_given(session, tenant):
    from app.services import limits

    payload = limits.build_param_payload(tenant, hidden_modules={"hotel"})
    assert payload[limits.HIDDEN_MODULES_PARAM] == "hotel"


def test_plan_allows_module_agrees_with_the_service(session, tenant):
    assert plan_service.plan_allows_module(tenant.plan, "sale_management") is True
    assert plan_service.plan_allows_module(tenant.plan, "hotel") is False
