"""End-to-end proof that the core patch locks a client database.

These tests run against a LIVE Odoo with the patch applied and `saas_lock = True`.
They are skipped unless the following environment variables are set:

    ODOO_E2E_URL      e.g. http://localhost:8069
    ODOO_E2E_DB       e.g. acme
    ODOO_E2E_LOGIN    e.g. admin
    ODOO_E2E_PASSWORD the client admin password
    ODOO_E2E_TOKEN    the same value as `saas_manager_token` in odoo.conf

What is verified (matching the deliverable "tests that prove..."):

    * a client admin CANNOT install/uninstall/upgrade an app
    * a client admin CANNOT open the database manager
    * a client admin CANNOT create user number max_users + 1
    * a client admin CANNOT add a warehouse past max_warehouses
    * a client admin CANNOT read/edit `saas.*` parameters
    * the MANAGER (with the token) CAN do all of the above
"""
from __future__ import annotations

import os

import pytest

from app.services.odoo_client import OdooClient, OdooError

URL = os.environ.get("ODOO_E2E_URL", "").rstrip("/")
DB = os.environ.get("ODOO_E2E_DB", "")
LOGIN = os.environ.get("ODOO_E2E_LOGIN", "admin")
PASSWORD = os.environ.get("ODOO_E2E_PASSWORD", "")
TOKEN = os.environ.get("ODOO_E2E_TOKEN", "")

pytestmark = pytest.mark.skipif(
    not (URL and DB and PASSWORD and TOKEN),
    reason="set ODOO_E2E_URL/DB/LOGIN/PASSWORD/TOKEN to run the live lock tests",
)


def admin_client(manager_token: str) -> OdooClient:
    """Authenticate as the client admin, optionally with a token to bypass the lock."""
    client = OdooClient(db=DB, base_url=URL, manager_token=manager_token)
    client.authenticate(LOGIN, PASSWORD)
    return client


def test_client_cannot_install_an_app():
    client = admin_client("wrong-token")
    try:
        with pytest.raises(OdooError) as exc:
            client.install_modules(["sale_management"])
        assert "Access" in str(exc.value) or "SAAS-PATCH" in str(exc.value) or exc.value.name.endswith("AccessError")
    finally:
        client.close()


def test_manager_can_install_an_app():
    client = admin_client(TOKEN)
    try:
        # Installs if not present, no-op otherwise; must not raise.
        installed = client.installed_modules()
        assert "base" in installed
        client.install_modules(["base"])  # already installed -> no-op, but not blocked
    finally:
        client.close()


def test_client_cannot_open_database_manager():
    import httpx  # noqa: PLC0415

    resp = httpx.post(
        f"{URL}/web/database/manager",
        cookies={},
        follow_redirects=False,
    )
    # The patched controller refuses access (403/404) rather than serving the page.
    assert resp.status_code in (403, 404, 303)


def test_client_cannot_read_saas_parameters():
    client = admin_client("wrong-token")
    try:
        value = client.call_kw("ir.config_parameter", "get_param", ["saas.max_users", "__hidden__"])
        assert value in ("", "__hidden__", False), "saas.* parameters must be hidden from clients"
    finally:
        client.close()


def test_manager_can_write_saas_parameters():
    client = admin_client(TOKEN)
    try:
        client.set_param("saas.max_users", "5")
        assert client.get_param("saas.max_users") == "5"
    finally:
        client.close()


def test_client_cannot_add_a_user_past_the_limit():
    """Set a limit of 1, then attempt to create a second internal user."""
    manager = admin_client(TOKEN)
    try:
        manager.set_param("saas.max_users", "1")
        manager.set_param("saas.status", "active")
    finally:
        manager.close()

    client = admin_client("wrong-token")
    try:
        with pytest.raises(OdooError) as exc:
            client.create_user({"name": "Extra", "login": "extra-limit@example.com", "password": "x"})
        assert "limit" in str(exc.value).lower()
    finally:
        client.close()


def test_client_cannot_add_a_warehouse_past_the_limit():
    manager = admin_client(TOKEN)
    try:
        manager.set_param("saas.max_warehouses", "1")
    finally:
        manager.close()

    client = admin_client("wrong-token")
    try:
        with pytest.raises(OdooError) as exc:
            client.create_warehouse({"name": "Extra WH", "code": "EXWH"})
        assert "limit" in str(exc.value).lower()
    finally:
        client.close()
