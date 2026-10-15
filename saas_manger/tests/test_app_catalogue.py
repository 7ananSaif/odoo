"""The app catalogue, the bouquet ladder, and the white-label plan.

These tests pin the product rule the operator asked for: **every app belongs to
a bouquet**. A catalogue app that no plan lists could never be installed for a
tenant, so the ladder must stay complete and monotonic, and one plan must be
white-label so apps added later are covered too.
"""
from __future__ import annotations

from app.services import app_catalogue, plan_service


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------
def test_catalogue_is_not_empty_and_unique():
    names = app_catalogue.catalogue()
    assert names
    assert len(names) == len(set(names))
    assert "base" in app_catalogue.BASE_MODULES
    assert "saas_tenant_guard" in app_catalogue.BASE_MODULES


def test_ladder_has_at_least_ten_bouquets():
    rows = app_catalogue.plan_rows()
    assert len(rows) == len(app_catalogue.TIER_APPS)
    assert len(rows) >= 10


def test_ladder_is_complete_and_monotonic():
    """No catalogue app is left out, and a plan never loses an app below it."""
    assert app_catalogue.ladder_problems() == []
    assert app_catalogue.uncovered() == []


def test_every_plan_inherits_the_plan_below_it():
    rows = app_catalogue.plan_rows()
    previous: set[str] = set()
    for row in rows:
        modules = set(row["modules"])
        assert previous <= modules, f"{row['code']} dropped apps from the plan below"
        previous = modules


def test_last_bouquet_is_white_label_and_lists_the_whole_catalogue():
    rows = app_catalogue.plan_rows()
    last = rows[-1]
    assert last["all_apps"] is True
    assert set(app_catalogue.catalogue()) <= set(last["modules"])


def test_coverage_maps_every_app_to_at_least_one_plan():
    covered = app_catalogue.coverage()
    for name in app_catalogue.catalogue():
        assert covered.get(name), f"{name} is not in any bouquet"


def test_ladder_problems_reports_a_missing_app():
    """A catalogue the tiers do not all reach is reported, not silently passed."""
    rows = app_catalogue.plan_rows()
    rows[-1]["modules"] = [name for name in rows[-1]["modules"] if name != "hotel"]
    rows[-1]["all_apps"] = False
    problems = app_catalogue.ladder_problems(rows)
    assert any("hotel" in problem for problem in problems)


# ---------------------------------------------------------------------------
# Real plans (models) — the white-label flag and module gating
# ---------------------------------------------------------------------------
def _plan(all_apps: bool, modules: list[str]):
    from app.models.plan import Plan, PlanModule

    plan = Plan(name="t", code="t", all_apps=all_apps)
    plan.modules = [PlanModule(technical_name=name) for name in modules]
    return plan


def test_allowed_modules_always_keeps_base_and_web():
    allowed = plan_service.allowed_modules(_plan(False, ["sale_management"]))
    assert {"base", "web", "sale_management"} <= allowed


def test_white_label_plan_allows_any_app():
    plan = _plan(True, ["sale_management"])
    assert plan_service.allows_all(plan) is True
    assert plan_service.plan_allows_module(plan, "hotel") is True
    assert plan_service.plan_allows_module(plan, "library") is True


def test_listed_plan_only_allows_its_own_apps():
    plan = _plan(False, ["sale_management"])
    assert plan_service.allows_all(plan) is False
    assert plan_service.plan_allows_module(plan, "sale_management") is True
    assert plan_service.plan_allows_module(plan, "hotel") is False


def test_manual_extra_overrides_the_plan():
    """A manual activation makes an app installable without touching the plan."""
    plan = _plan(False, ["sale_management"])
    assert plan_service.plan_allows_module(plan, "hotel") is False
    assert plan_service.plan_allows_module(plan, "hotel", extra={"hotel"}) is True


def test_no_plan_allows_nothing_beyond_base_and_web():
    assert plan_service.plan_allows_module(None, "web") is True
    assert plan_service.plan_allows_module(None, "hotel") is False


def test_white_label_plan_never_uninstalls_anything():
    plan = _plan(True, ["sale_management"])
    diff = plan_service.compute_diff({"account", "sale_management", "hotel"}, plan)
    assert diff.to_uninstall == []
    assert diff.to_install == ["base", "web"]


def test_listed_plan_uninstalls_what_it_does_not_allow():
    plan = _plan(False, ["sale_management"])
    diff = plan_service.compute_diff({"base", "web", "sale_management", "hotel"}, plan)
    assert diff.to_uninstall == ["hotel"]


# ---------------------------------------------------------------------------
# Applying a plan must not undo a manual activation
# ---------------------------------------------------------------------------
class _FakeClient:
    """Just enough of an OdooClient for apply_plan."""

    def __init__(self, installed: list[str]):
        self._installed = set(installed)
        self.installed: list[str] = []
        self.uninstalled: list[str] = []

    def installed_modules(self) -> list[str]:
        return sorted(self._installed)

    def install_modules(self, names: list[str]):
        self.installed.extend(names)
        self._installed |= set(names)
        return names

    def uninstall_modules(self, names: list[str]):
        self.uninstalled.extend(names)
        self._installed -= set(names)
        return names


def test_apply_plan_removes_what_the_plan_forbids():
    plan = _plan(False, ["sale_management"])
    client = _FakeClient(["base", "web", "sale_management", "hotel"])

    diff = plan_service.apply_plan(client, plan)

    assert diff.to_uninstall == ["hotel"]
    assert client.uninstalled == ["hotel"]
    assert "hotel" not in client.installed_modules()


def test_apply_plan_keeps_manually_activated_apps():
    """A plan change must not silently undo an operator's activation."""
    plan = _plan(False, ["sale_management"])
    client = _FakeClient(["base", "web", "sale_management", "hotel"])

    diff = plan_service.apply_plan(client, plan, keep={"hotel"})

    assert diff.to_uninstall == []
    assert client.uninstalled == []
    assert "hotel" in client.installed_modules()


def test_apply_plan_on_a_white_label_plan_removes_nothing():
    plan = _plan(True, ["sale_management"])
    client = _FakeClient(["base", "web", "sale_management", "hotel", "library"])

    diff = plan_service.apply_plan(client, plan)

    assert diff.to_uninstall == []
    assert client.uninstalled == []
    assert {"hotel", "library"} <= set(client.installed_modules())
