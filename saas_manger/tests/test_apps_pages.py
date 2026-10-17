"""The app and bouquet screens must render with the data the routes provide.

Rendering the real Jinja templates with realistic context catches the mistakes
that type-checking cannot: a variable the route forgot to pass, a filter that
does not exist, an attribute a model does not have.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.models.plan import Plan, PlanModule
from app.models.tenant import Tenant
from app.services import app_catalogue, odoo_apps
from app.web.routes_plans import _coverage
from app.web.templating import templates


class _Url:
    def __init__(self, path: str):
        self.path = path


class _Request:
    """The handful of attributes ``base.html`` reads."""

    def __init__(self, path: str):
        self.url = _Url(path)
        self.query_params: dict[str, str] = {}
        self.state = SimpleNamespace(user=None)


def _render(template: str, context: dict) -> str:
    data = {
        "request": _Request("/plans"),
        "user": SimpleNamespace(name="Owner", email="owner@example.com"),
        "app_name": "SaaS Manager",
        "app_version": "test",
        "flash": "",
        "error": "",
        "settings": SimpleNamespace(),
        "can": lambda permission: True,
    }
    data.update(context)
    return templates.env.get_template(template).render(data)


def _plan(code: str, modules: list[str], *, all_apps: bool = False) -> Plan:
    plan = Plan(name=code.title(), code=code, all_apps=all_apps, currency="USD")
    plan.modules = [PlanModule(technical_name=name) for name in modules]
    return plan


def _app(name: str, *, installed: bool, label: str = "") -> odoo_apps.AppInfo:
    return odoo_apps.AppInfo(
        name=name, label=label or name.title(), summary="", category="Sales",
        state="installed" if installed else "uninstalled", installed_version="19.0",
        latest_version="19.0", is_app=True, author="Odoo",
    )


# ---------------------------------------------------------------------------
# Bouquets
# ---------------------------------------------------------------------------
def test_plans_list_renders_the_coverage_banner(session):
    starter = _plan("starter", ["sale_management"])
    everything = _plan("everything", app_catalogue.catalogue(), all_apps=True)
    session.add_all([starter, everything])
    session.flush()

    html = _render("plans/list.html", {"plans": [starter, everything], "coverage": _coverage(session)})

    assert "Every app belongs to a bouquet" in html
    assert "all apps" in html               # the white-label badge
    assert "every app" in html
    assert "/plans/coverage" in html


def test_plans_list_flags_apps_with_no_bouquet(session):
    starter = _plan("starter", ["sale_management"])
    session.add(starter)
    session.flush()

    html = _render("plans/list.html", {"plans": [starter], "coverage": _coverage(session)})

    assert "belong to no bouquet" in html
    assert "hotel" in html  # the first uncovered catalogue app it names


def test_coverage_page_lists_every_catalogue_app(session):
    everything = _plan("everything", app_catalogue.catalogue(), all_apps=True)
    session.add(everything)
    session.flush()

    html = _render("plans/coverage.html", _coverage(session))

    assert str(len(app_catalogue.catalogue())) in html
    assert "white-label" in html
    for name in ("hotel", "library", "sale_management", "saas_tenant_guard"):
        assert name in html, f"{name} missing from the coverage page"


def test_coverage_page_reports_an_incomplete_database(session):
    starter = _plan("starter", ["sale_management"])
    session.add(starter)
    session.flush()

    html = _render("plans/coverage.html", _coverage(session))
    assert "belong to no bouquet" in html


def test_plan_form_shows_the_white_label_switch(session):
    plan = _plan("everything", ["sale_management"], all_apps=True)
    session.add(plan)
    session.flush()  # the form links to /plans/<id>/edit, so the row needs an id

    html = _render("plans/form.html", {"plan": plan, "modules_raw": "sale_management"})
    assert 'name="all_apps"' in html
    assert "checked" in html


# ---------------------------------------------------------------------------
# A tenant's apps
# ---------------------------------------------------------------------------
def _apps_context(
    session,
    *,
    plan,
    all_apps: bool = False,
    hidden: set[str] | None = None,
    manual: set[str] | None = None,
):
    tenant = Tenant(name="Acme", subdomain="acme", db_name="acme", provisioned=True)
    session.add(tenant)
    session.flush()
    listed = set(plan.module_names) if plan else {"base", "web"}
    hidden = hidden or set()
    manual = manual or set()
    return {
        "tenant": tenant,
        "plan": plan,
        "apps": [
            _app("base", installed=True),
            _app("sale_management", installed=True),
            _app("hotel", installed=False, label="Hotel"),
        ],
        "total": 3,
        "installed_count": 2,
        "allowed": listed | manual,
        "listed": listed,
        "manual": manual,
        "hidden": hidden,
        "overrides": {},
        "plan_allows_all": all_apps,
        "catalogue_allowed": sorted(listed),
        "plan_app_count": len(listed),
        "orphaned": [],
        "catalogue_size": len(app_catalogue.catalogue()),
        "menu_active": 0,
        "guard_installed": True,
        "q": "",
        "filter": "all",
        "load_error": "",
        "can_manage": True,
    }


def test_apps_page_offers_install_activate_and_hide(session):
    """An app outside the bouquet gets the manual-activation button."""
    plan = _plan("starter", ["sale_management"])
    session.add(plan)
    session.flush()

    html = _render("apps/modules.html", _apps_context(session, plan=plan))

    assert "/hotel/activate" in html            # manual activation is offered
    assert "Activate for this tenant" in html
    assert "not in this bouquet" in html
    assert "in bouquet" in html                 # sale_management is listed
    assert "/sale_management/hide" in html      # an installed, removable app can be hidden


def test_apps_page_installs_an_activated_app(session):
    """Once activated, the app is installable — the button becomes Install."""
    plan = _plan("starter", ["sale_management"])
    session.add(plan)
    session.flush()

    html = _render("apps/modules.html", _apps_context(session, plan=plan, manual={"hotel"}))

    assert "/hotel/install" in html
    assert "activated" in html
    assert "/hotel/deactivate" in html
    assert "/hotel/activate" not in html


def test_apps_page_marks_a_hidden_app(session):
    plan = _plan("starter", ["sale_management"])
    session.add(plan)
    session.flush()

    html = _render("apps/modules.html",
                   _apps_context(session, plan=plan, hidden={"sale_management"}))

    assert "hidden" in html
    assert "/sale_management/unhide" in html
    assert "/sale_management/hide" not in html


def test_apps_page_shows_the_orphan_banner(session):
    plan = _plan("starter", ["sale_management"])
    session.add(plan)
    session.flush()

    context = _apps_context(session, plan=plan)
    context["orphaned"] = ["hotel"]
    html = _render("apps/modules.html", context)

    assert "Not part of any bouquet" in html
    assert "/hotel/add-to-bouquet" in html


def test_apps_index_renders_with_override_counts(session):
    everything = _plan("everything", ["sale_management"], all_apps=True)
    session.add(everything)
    session.flush()
    tenant = Tenant(name="Acme", subdomain="acme", db_name="acme", provisioned=True,
                    plan_id=everything.id)
    session.add(tenant)
    session.flush()

    html = _render("apps/list.html", {"tenants": [tenant], "overrides": {tenant.id: 2}})

    assert "Acme" in html
    assert "white-label" in html
    assert "2 app decision(s)" in html
