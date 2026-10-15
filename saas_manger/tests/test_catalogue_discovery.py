"""Automatic catalogue discovery and the white-label backfill.

An app must never be second-class because it was not in the shipped catalogue.
These tests pin the behaviour the operator asked for: any application a server
reports is registered on its own, adopted by the white-label bouquet, and — when
the ``all_apps`` column is added to a database that predates it — the bouquet
that is meant to be white-label actually becomes one.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text

import app.db as db
from app.models.plan import Plan, PlanModule
from app.services import app_catalogue, catalogue_service, odoo_apps


def _app(name: str, *, is_app: bool = True, label: str = "") -> odoo_apps.AppInfo:
    return odoo_apps.AppInfo(
        name=name, label=label or name.title(), summary="", category="",
        state="uninstalled", installed_version="", latest_version="",
        is_app=is_app, author="",
    )


@pytest.fixture()
def white_label(session):
    plan = Plan(name="Everything", code="everything-test", all_apps=True)
    plan.modules = [PlanModule(technical_name="sale_management")]
    session.add(plan)
    session.flush()
    return plan


@pytest.fixture()
def plain_plan(session):
    plan = Plan(name="Starter", code="starter-discovery-test", all_apps=False)
    plan.modules = [PlanModule(technical_name="sale_management")]
    session.add(plan)
    session.flush()
    return plan


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
def test_discover_records_a_new_application(session):
    added = catalogue_service.discover(session, [_app("my_custom_app")])

    assert added == ["my_custom_app"]
    assert catalogue_service.discovered_names(session) == {"my_custom_app"}


def test_discover_skips_technical_modules(session):
    """A dependency Odoo pulls in is not something the manager sells."""
    added = catalogue_service.discover(session, [_app("auth_ldap", is_app=False)])

    assert added == []
    assert catalogue_service.discovered_names(session) == set()


def test_discover_skips_apps_the_catalogue_already_knows(session):
    shipped = app_catalogue.catalogue()[0]
    added = catalogue_service.discover(session, [_app(shipped)])

    assert added == []
    assert catalogue_service.discovered_names(session) == set()


def test_discover_is_idempotent(session):
    catalogue_service.discover(session, [_app("my_custom_app")])
    added = catalogue_service.discover(session, [_app("my_custom_app")])

    assert added == []
    assert len(catalogue_service.list_discovered(session)) == 1


def test_discover_skips_a_blank_name(session):
    assert catalogue_service.discover(session, [_app("   ")]) == []


def test_known_names_include_discoveries(session):
    before = catalogue_service.known_names(session)
    catalogue_service.discover(session, [_app("my_custom_app")])
    after = catalogue_service.known_names(session)

    assert "my_custom_app" not in before
    assert after == before | {"my_custom_app"}
    assert catalogue_service.is_known(session, "my_custom_app") is True


# ---------------------------------------------------------------------------
# Adoption into the white-label bouquet
# ---------------------------------------------------------------------------
def test_adopt_adds_the_app_to_the_white_label_bouquet(session, white_label):
    plan = catalogue_service.adopt(session, ["my_custom_app"])

    assert plan is not None and plan.code == white_label.code
    assert "my_custom_app" in {m.technical_name for m in plan.modules}


def test_adopt_is_idempotent(session, white_label):
    catalogue_service.adopt(session, ["my_custom_app"])
    catalogue_service.adopt(session, ["my_custom_app"])

    names = [m.technical_name for m in white_label.modules]
    assert names.count("my_custom_app") == 1


def test_adopt_without_a_white_label_bouquet_changes_nothing(session, plain_plan):
    assert catalogue_service.adopt(session, ["my_custom_app"]) is None


def test_sync_discovers_and_adopts_in_one_step(session, white_label):
    added = catalogue_service.sync(
        session, [_app("my_custom_app"), _app("auth_ldap", is_app=False)],
        source="tenant_db",
    )

    assert added == ["my_custom_app"]
    assert catalogue_service.discovered_names(session) == {"my_custom_app"}
    assert "my_custom_app" in {m.technical_name for m in white_label.modules}


def test_a_discovered_app_installs_under_the_white_label_bouquet(session, white_label):
    """The whole point: a new app becomes installable without editing a plan."""
    catalogue_service.sync(session, [_app("my_custom_app")])

    assert odoo_apps.plan_allows(white_label, "my_custom_app") is True


# ---------------------------------------------------------------------------
# The rescan call
# ---------------------------------------------------------------------------
class _FakeClient:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def call_kw(self, model, method, args=None, kwargs=None):
        self.calls.append((model, method))
        if method == "search_read":
            return [{
                "name": "my_custom_app", "shortdesc": "My App", "summary": "",
                "category_id": False, "state": "uninstalled", "application": True,
                "installed_version": "", "latest_version": "", "author": "",
            }]
        return True


def test_refresh_module_list_updates_and_reports_the_count():
    client = _FakeClient()

    count = odoo_apps.refresh_module_list(client)

    assert ("ir.module.module", "update_list") in client.calls
    assert count == 1


# ---------------------------------------------------------------------------
# The white-label backfill on a database that predates the column
# ---------------------------------------------------------------------------
def test_migration_flags_the_white_label_bouquet():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, is_superuser BOOLEAN, role VARCHAR(16))"
        )
        conn.exec_driver_sql("CREATE TABLE plans (id INTEGER PRIMARY KEY, code VARCHAR(64))")
        conn.exec_driver_sql(
            "INSERT INTO plans (id, code) VALUES (1, 'starter'), (2, 'everything')"
        )

    with engine.begin() as conn:
        db._migrate(conn)
        assert "all_apps" in {c["name"] for c in inspect(conn).get_columns("plans")}
        rows = conn.execute(text("SELECT code, all_apps FROM plans ORDER BY id")).fetchall()

    assert rows == [("starter", 0), ("everything", 1)]

    # Re-running must not touch the operator's own choice any more.
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE plans SET all_apps = 0 WHERE code = 'everything'")
    with engine.begin() as conn:
        db._migrate(conn)
        value = conn.execute(
            text("SELECT all_apps FROM plans WHERE code = 'everything'")
        ).scalar()
    assert value == 0
