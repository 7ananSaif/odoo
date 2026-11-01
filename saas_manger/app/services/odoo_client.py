"""Client for talking to Odoo instances (the SaaS Manager side).

Two transports are supported and share the same manager token:

* **Odoo RPC** (``/web/session/authenticate`` + ``/web/dataset/call_kw``) using a
  login/password. This is the bootstrap path: it works from the first call and
  lets the manager create users, companies, warehouses, push ``saas.*`` params,
  install/uninstall modules, etc.
* **JSON-2** (``POST /json/2/<model>/<method>`` with ``Authorization: Bearer``)
  when a per-tenant API key is available. Verified to exist in Odoo 19.

Every request carries ``X-Saas-Manager-Token`` and passes the same value in the
RPC ``context`` so the core ``# SAAS-PATCH`` guard recognises an authorised call.
"""
from __future__ import annotations

import itertools
import logging
import xmlrpc.client
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings

_logger = logging.getLogger(__name__)
_ids = itertools.count(1)


class OdooError(RuntimeError):
    """Any error returned by Odoo (auth, access, validation, protocol)."""

    def __init__(self, message: str, *, name: str = "", data: Any = None):
        super().__init__(message)
        self.name = name
        self.data = data


@dataclass
class OdooClient:
    """A short-lived client bound to one database."""

    db: str
    base_url: str = field(default_factory=lambda: settings.odoo_base_url.rstrip("/"))
    manager_token: str = field(default_factory=lambda: settings.odoo_manager_token)
    timeout: float = field(default_factory=lambda: float(settings.odoo_request_timeout))
    uid: int | None = None
    api_key: str | None = None
    _client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"X-Saas-Manager-Token": self.manager_token},
            follow_redirects=True,
        )

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OdooClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- session hand-off (browser auto-login) -----------------------------
    @property
    def session_id(self) -> str | None:
        """The Odoo ``session_id`` cookie from the latest response, if any."""
        return self._client.cookies.get("session_id")

    def open_session(self, login: str, password: str) -> str:
        """Authenticate and return the Odoo session id.

        The id can be handed to a browser as the ``session_id`` cookie so it
        lands inside Odoo already signed in (see :mod:`app.services.odoo_login`).
        """
        self.authenticate(login, password)
        session_id = self.session_id
        if not session_id:
            raise OdooError("Odoo did not return a session_id cookie")
        return session_id

    # -- helpers -----------------------------------------------------------
    def _context(self, extra: dict | None = None) -> dict:
        """Base RPC context, always carrying the manager token."""
        ctx = {"lang": "en_US", "saas_manager_token": self.manager_token}
        if extra:
            ctx.update(extra)
        return ctx

    @staticmethod
    def _raise_from_error(err: dict) -> None:
        data = err.get("data", {}) if isinstance(err, dict) else {}
        message = data.get("message") or err.get("message") or "Odoo error"
        name = data.get("name") or err.get("name", "")
        raise OdooError(message, name=name, data=data)

    # -- transport 1: session + /web/dataset/call_kw -----------------------
    def authenticate(self, login: str, password: str) -> int:
        """Open a session; store and return the uid."""
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"db": self.db, "login": login, "password": password},
            "id": next(_ids),
        }
        resp = self._client.post("/web/session/authenticate", json=payload)
        body = resp.json()
        if body.get("error"):
            self._raise_from_error(body["error"])
        result = body.get("result") or {}
        uid = result.get("uid")
        if not uid:
            raise OdooError("Authentication failed: no uid returned")
        self.uid = int(uid)
        return self.uid

    def call_kw(self, model: str, method: str, args: list | None = None, kwargs: dict | None = None) -> Any:
        """Call a model method over the classic RPC, injecting the token context."""
        if self.uid is None and self.api_key is None:
            raise OdooError("Not authenticated: call authenticate() or set an api_key first")
        kwargs = dict(kwargs or {})
        kwargs["context"] = self._context(kwargs.get("context"))
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"model": model, "method": method, "args": args or [], "kwargs": kwargs},
            "id": next(_ids),
        }
        resp = self._client.post("/web/dataset/call_kw", json=payload)
        body = resp.json()
        if body.get("error"):
            self._raise_from_error(body["error"])
        return body.get("result")

    # -- transport 2: JSON-2 with an API key -------------------------------
    def json2(self, model: str, method: str, payload: dict | None = None, ids: list | None = None) -> Any:
        """Call a model method over JSON-2 using the configured API key."""
        if not self.api_key:
            raise OdooError("No API key configured for JSON-2 calls")
        body = dict(payload or {})
        if ids is not None:
            body["ids"] = ids
        resp = self._client.post(
            f"/json/2/{model}/{method}",
            json=body,
            headers={"Authorization": f"Bearer {self.api_key}", "X-Odoo-Database": self.db},
        )
        if resp.status_code >= 400:
            try:
                err = resp.json()
            except ValueError:
                raise OdooError(f"JSON-2 HTTP {resp.status_code}: {resp.text[:200]}")
            self._raise_from_error(err)
        return resp.json()

    # -- transport 3: XML-RPC db service -----------------------------------
    def db_call(self, method: str, params: list) -> Any:
        """Call the Odoo ``db`` service (create/drop/backup/...). Needs the manager token."""
        xml = xmlrpc.client.dumps(tuple(params), methodname=method, allow_none=True)
        resp = self._client.post(
            "/xmlrpc/2/db",
            content=xml.encode(),
            headers={"Content-Type": "text/xml"},
        )
        try:
            result, _ = xmlrpc.client.loads(resp.text)
        except xmlrpc.client.Fault as fault:  # pragma: no cover - defensive
            raise OdooError(fault.faultString) from fault
        return result[0] if result else None

    # -- high level operations ---------------------------------------------
    def create_database(
        self,
        db_name: str,
        *,
        demo: bool = False,
        lang: str = "en_US",
        admin_password: str = "admin",
        admin_login: str = "admin",
        country_code: str | None = None,
        phone: str | None = None,
    ) -> bool:
        """Ask Odoo to create and initialise a fresh database."""
        return bool(self.db_call("create_database", [
            settings.odoo_master_password,
            db_name,
            demo,
            lang,
            admin_password,
            admin_login,
            country_code or False,
            phone or False,
        ]))

    def duplicate_database(self, source: str, target: str, neutralize: bool = False) -> bool:
        return bool(self.db_call("duplicate_database", [
            settings.odoo_master_password, source, target, neutralize,
        ]))

    def drop_database(self, db_name: str) -> bool:
        return bool(self.db_call("drop", [settings.odoo_master_password, db_name]))

    def list_databases(self) -> list[str]:
        try:
            return list(self.db_call("list", []) or [])
        except OdooError:
            return []

    def database_exists(self, db_name: str) -> bool:
        return bool(self.db_call("db_exist", [db_name]))

    def server_version(self) -> str:
        try:
            return str(self.db_call("server_version", []))
        except OdooError:
            return ""

    # -- module management --------------------------------------------------
    def installed_modules(self) -> list[str]:
        rows = self.call_kw(
            "ir.module.module", "search_read",
            [[("state", "=", "installed")], ["name"]],
            {"context": self._context()},
        )
        return [r["name"] for r in rows]

    def install_modules(self, module_names: list[str]) -> Any:
        """Install modules immediately (manager-token authorised)."""
        ids = self.call_kw(
            "ir.module.module", "search",
            [[("name", "in", module_names), ("state", "=", "uninstalled")]],
        )
        if not ids:
            return []
        return self.call_kw("ir.module.module", "button_immediate_install", [ids])

    def uninstall_modules(self, module_names: list[str]) -> Any:
        ids = self.call_kw(
            "ir.module.module", "search",
            [[("name", "in", module_names), ("state", "=", "installed")]],
        )
        if not ids:
            return []
        return self.call_kw("ir.module.module", "button_immediate_uninstall", [ids])

    # -- configuration parameters ------------------------------------------
    def set_param(self, key: str, value: str) -> None:
        self.call_kw("ir.config_parameter", "set_param", [key, value])

    def get_param(self, key: str, default: str = "") -> str:
        return self.call_kw("ir.config_parameter", "get_param", [key, default]) or default

    def push_saas_params(self, params: dict[str, Any]) -> None:
        """Write the given ``saas.*`` parameters into the client database."""
        for key, value in params.items():
            self.set_param(key, "" if value is None else str(value))

    # -- users --------------------------------------------------------------
    def search_users(self, domain: list) -> list[dict]:
        return self.call_kw("res.users", "search_read", [domain, ["id", "login", "name", "active", "share"]])

    def create_user(self, values: dict) -> int:
        return self.call_kw("res.users", "create", [values])

    def write_user(self, user_id: int, values: dict) -> bool:
        return bool(self.call_kw("res.users", "write", [[user_id], values]))

    def set_user_password(self, user_id: int, password: str) -> bool:
        return self.write_user(user_id, {"password": password})

    def set_user_groups(self, user_id: int, group_xmlids: list[str]) -> bool:
        """Assign access groups (from templates) to a user."""
        return bool(self.call_kw(
            "res.users", "write",
            [[user_id], {"group_ids": [(6, 0, self._group_ids(group_xmlids))]}],
        ))

    def _group_ids(self, group_xmlids: list[str]) -> list[int]:
        ids: list[int] = []
        for xmlid in group_xmlids:
            module, _, name = xmlid.partition(".")
            found = self.call_kw(
                "ir.model.data", "search",
                [[("module", "=", module), ("name", "=", name), ("model", "=", "res.groups")]],
            )
            ids.extend(found or [])
        return ids

    # -- companies / warehouses --------------------------------------------
    def create_company(self, values: dict) -> int:
        return self.call_kw("res.company", "create", [values])

    def create_warehouse(self, values: dict) -> int:
        return self.call_kw("stock.warehouse", "create", [values])

    # -- health -------------------------------------------------------------
    def ping(self) -> bool:
        """Return True if the instance answers with a version string."""
        try:
            return bool(self.server_version())
        except Exception:  # noqa: BLE001
            return False
