"""End-to-end check of the SaaS Manager's users, roles, plans, tenants and Odoo tools.

Run it *inside* the `saas-manager-web` container, where the app and its
dependencies are importable and the panel answers on ``127.0.0.1:8080``:

```bash
docker compose --profile saas-manager exec -T saas-manager-web \
    python scripts/verify_features.py
```

From the host, pipe it in (Windows PowerShell and Unix shells both work):

```bash
Get-Content saas_manger/scripts/verify_features.py -Raw | \
    docker compose --profile saas-manager exec -T saas-manager-web python -
```

What it covers:

* the pure role → permission matrix, and that an unknown role degrades to viewer;
* the cookie-domain rules behind "Open in Odoo";
* that an owner can open every section, and all five seeded plans are visible;
* creating one account per role and the resulting ``role`` / ``is_superuser``;
* role enforcement over real HTTP (403s where a role lacks a permission);
* the write guards (viewer cannot create plans, operator cannot save settings);
* the self-protection rails (no self-deactivation, no self-deletion, last owner);
* the tenant page's Test Odoo / Open in Odoo controls, a live ``Test Odoo``
  call against a provisioned database, and the auto-login session hand-off.

The accounts it creates (``admin@operator@viewer@example.com``) and the plan
``admin-made`` are removed at the start of every run, so it is repeatable. It
never deletes tenants, and the last-owner check runs inside a rolled-back
transaction.

Exit code is 0 when every check passed, 1 otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User  # noqa: E402
from app.security import create_session_token  # noqa: E402
from app.services import odoo_login, permissions as perms  # noqa: E402

BASE_URL = "http://127.0.0.1:8080"
TEST_PASSWORD = "ChangeMe-User-2026!"
TEST_ACCOUNTS = (
    ("admin@example.com", "Site Admin", "admin"),
    ("operator@example.com", "Operations", "operator"),
    ("viewer@example.com", "Read Only", "viewer"),
)
TEST_PLAN_CODE = "admin-made"

_passed = 0
_failed: list[str] = []


def check(label: str, condition: bool, extra: str = "") -> None:
    """Record and print one assertion."""
    global _passed
    if condition:
        _passed += 1
    else:
        _failed.append(label)
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {label}" + (f"  ({extra})" if extra else ""))


def session_client(email: str, timeout: float = 30.0) -> httpx.Client:
    """An HTTP client already holding a valid panel session for ``email``."""
    with SessionLocal() as session:
        user = session.query(User).filter(User.email == email).one()
        user_id = user.id
    return httpx.Client(
        base_url=BASE_URL,
        cookies={settings.session_cookie: create_session_token(user_id, email)},
        follow_redirects=False,
        timeout=timeout,
    )


def reset_test_data() -> None:
    """Drop leftovers from an earlier run so the script stays repeatable."""
    from app.models.plan import Plan

    with SessionLocal() as session:
        session.query(User).filter(
            User.email.in_([account[0] for account in TEST_ACCOUNTS] + ["weak@example.com"])
        ).delete(synchronize_session=False)
        session.query(Plan).filter(Plan.code == TEST_PLAN_CODE).delete(synchronize_session=False)
        session.commit()


def check_permission_matrix() -> None:
    print("\n== permission matrix (pure) ==")
    check("owner manages users", perms.has_permission("owner", perms.PERM_USERS_MANAGE))
    check("admin cannot manage users", not perms.has_permission("admin", perms.PERM_USERS_MANAGE))
    check("admin cannot change settings",
          not perms.has_permission("admin", perms.PERM_SETTINGS_MANAGE))
    check("admin deletes tenants", perms.has_permission("admin", perms.PERM_TENANTS_DELETE))
    check("operator manages tenants", perms.has_permission("operator", perms.PERM_TENANTS_MANAGE))
    check("operator cannot delete tenants",
          not perms.has_permission("operator", perms.PERM_TENANTS_DELETE))
    check("operator takes backups", perms.has_permission("operator", perms.PERM_BACKUPS_MANAGE))
    check("viewer cannot manage tenants",
          not perms.has_permission("viewer", perms.PERM_TENANTS_MANAGE))
    check("viewer views finance", perms.has_permission("viewer", perms.PERM_FINANCE_VIEW))
    check("viewer cannot manage finance",
          not perms.has_permission("viewer", perms.PERM_FINANCE_MANAGE))
    check("unknown role degrades to viewer", perms.normalize_role("superuser") == "viewer")


def check_cookie_domain_rules() -> None:
    print("\n== auto-login cookie-domain rules (pure) ==")
    check("same host -> host-only cookie",
          odoo_login.cookie_domain_for("127.0.0.1:8090", "127.0.0.1") == "")
    check("shared domain -> parent cookie",
          odoo_login.cookie_domain_for("manager.example.com", "acme.example.com") == ".example.com")
    check("unrelated domains -> refused",
          odoo_login.cookie_domain_for("manager.example.com", "acme.other.com") is None)


def check_owner_sections() -> httpx.Client:
    owner = session_client("owner@example.com")
    print("\n== owner can open every section ==")
    for path in ["/", "/tenants", "/tenants/new", "/plans", "/plans/new",
                 "/updates", "/finance", "/settings", "/audit", "/users", "/users/new"]:
        response = owner.get(path)
        check(f"GET {path}", response.status_code == 200, f"HTTP {response.status_code}")

    print("\n== the five seeded bouquets are visible ==")
    plans_page = owner.get("/plans").text
    for code in ["starter", "professional", "business", "enterprise", "reseller"]:
        check(f"plan {code}", code in plans_page)

    print("\n== the users screen renders the role matrix ==")
    users_page = owner.get("/users").text
    for role in ["Owner", "Admin", "Operator", "Viewer"]:
        check(f"role {role} described", role in users_page)
    return owner


def check_account_creation(owner: httpx.Client) -> None:
    print("\n== create one account per role ==")
    for email, name, role in TEST_ACCOUNTS:
        response = owner.post("/users/new", data={
            "email": email, "name": name, "role": role,
            "password": TEST_PASSWORD, "password_confirm": TEST_PASSWORD,
        })
        check(f"create {role} account", response.status_code == 303,
              response.headers.get("location", ""))

    with SessionLocal() as session:
        for email, _name, role in TEST_ACCOUNTS:
            row = session.query(User).filter(User.email == email).one_or_none()
            check(f"{email} stored with role {role}",
                  row is not None and row.role == role)
            if row is not None:
                expected_superuser = role in ("owner", "admin")
                check(f"{email} is_superuser={expected_superuser}",
                      row.is_superuser == expected_superuser)

    duplicate = owner.post("/users/new", data={
        "email": TEST_ACCOUNTS[2][0], "name": "Dup", "role": "viewer",
        "password": TEST_PASSWORD, "password_confirm": TEST_PASSWORD,
    })
    check("duplicate email refused", "error=" in duplicate.headers.get("location", ""))

    weak = owner.post("/users/new", data={
        "email": "weak@example.com", "name": "Weak", "role": "viewer",
        "password": "short", "password_confirm": "short",
    })
    check("short password refused", "error=" in weak.headers.get("location", ""))


def check_role_enforcement() -> None:
    print("\n== role enforcement over HTTP ==")
    expectations = {
        "admin": {"/users": 403, "/settings": 403, "/tenants": 200, "/plans": 200,
                  "/updates": 200, "/finance": 200},
        "operator": {"/users": 403, "/settings": 403, "/updates": 200, "/finance": 200},
        "viewer": {"/users": 403, "/settings": 403, "/updates": 403, "/tenants": 200,
                   "/plans": 200, "/finance": 200},
    }
    for role, paths in expectations.items():
        client = session_client(f"{role}@example.com")
        for path, expected in paths.items():
            response = client.get(path)
            check(f"{role} GET {path} is {expected}", response.status_code == expected,
                  f"HTTP {response.status_code}")

    print("\n== write guards ==")
    viewer = session_client("viewer@example.com")
    response = viewer.post("/plans/new", data={"name": "X", "code": "x"})
    check("viewer cannot create a plan", "error=" in response.headers.get("location", ""))
    response = viewer.post("/finance/mark-overdue")
    check("viewer cannot write finance", response.status_code == 403,
          f"HTTP {response.status_code}")

    operator = session_client("operator@example.com")
    response = operator.post("/settings", data={"company_name": "Hacked"})
    check("operator cannot save settings", response.status_code == 403,
          f"HTTP {response.status_code}")
    response = operator.post("/plans/new", data={"name": "Y", "code": "y"})
    check("operator cannot create a plan", "error=" in response.headers.get("location", ""))

    admin = session_client("admin@example.com")
    response = admin.post("/plans/new", data={
        "name": "Admin Made", "code": TEST_PLAN_CODE, "max_users": 2, "price_month": "5",
    })
    check("admin can create a plan",
          response.status_code == 303 and "error=" not in response.headers.get("location", ""),
          response.headers.get("location", ""))


def check_self_protection(owner: httpx.Client) -> None:
    print("\n== self-protection rails ==")
    with SessionLocal() as session:
        row = session.query(User).filter(User.email == "owner@example.com").one()
        owner_id = row.id
        active_owners = session.query(User).filter(
            User.role == "owner", User.is_active.is_(True)).count()

    response = owner.post(f"/users/{owner_id}/toggle-active")
    check("cannot deactivate your own account", "error=" in response.headers.get("location", ""))
    response = owner.post(f"/users/{owner_id}/delete")
    check("cannot delete your own account", "error=" in response.headers.get("location", ""))

    # Last-owner protection is asserted against the guard itself, inside a
    # transaction that is rolled back: going through HTTP would really demote
    # the account, and a demoted owner can no longer promote itself back.
    from app.web import routes_users

    with SessionLocal() as session:
        owner_row = session.query(User).filter(User.id == owner_id).one()
        check(f"owner is one of {active_owners} active owners",
              not routes_users._is_last_active_owner(session, owner_row))
        for other in session.query(User).filter(
            User.role == "owner", User.is_active.is_(True), User.id != owner_id,
        ).all():
            other.is_active = False
        session.flush()
        check("last active owner is detected",
              routes_users._is_last_active_owner(session, owner_row))
        session.rollback()

    with SessionLocal() as session:
        check("owner role unchanged after the check",
              session.get(User, owner_id).role == "owner")


def pick_tenant() -> tuple[int | None, str]:
    """Prefer a really-provisioned tenant so Test Odoo has something to hit."""
    with SessionLocal() as session:
        tenant = (session.query(Tenant)
                  .filter(Tenant.provisioned.is_(True))
                  .order_by(Tenant.id)
                  .first())
        if tenant is None:
            tenant = session.query(Tenant).order_by(Tenant.id).first()
        if tenant is None:
            return None, "none"
        return tenant.id, f"{tenant.subdomain} (provisioned={tenant.provisioned})"


def check_tenant_and_odoo(owner: httpx.Client) -> None:
    print("\n== tenant page, Test Odoo and auto-login ==")
    tenant_id, label = pick_tenant()
    print(f"  using tenant: {label}")

    if tenant_id is None:
        response = owner.post("/tenants/new", data={
            "name": "Acme", "subdomain": "acme", "plan_id": 0, "trial_days": 14,
        })
        check("created a tenant record", response.status_code == 303,
              response.headers.get("location", ""))
        location = response.headers.get("location", "/tenants/1")
        tenant_id = int(location.split("/")[2].split("?")[0])

    page = owner.get(f"/tenants/{tenant_id}")
    check("tenant page renders", page.status_code == 200, f"HTTP {page.status_code}")
    check("Test Odoo control present", "Test Odoo" in page.text)
    check("Open in Odoo control present", "Open in Odoo" in page.text)

    with SessionLocal() as session:
        provisioned = session.get(Tenant, tenant_id).provisioned

    if not provisioned:
        print("  (tenant has no database yet — provisioning now, this takes a minute)")
        response = owner.post(f"/tenants/{tenant_id}/provision", timeout=900.0)
        location = response.headers.get("location", "")
        check("provision succeeded", "error=" not in location, location[:160])
        with SessionLocal() as session:
            provisioned = session.get(Tenant, tenant_id).provisioned
        check("tenant marked provisioned", provisioned)

    if not provisioned:
        print("  (no provisioned tenant — skipping the live Odoo checks)")
        return

    print("\n== Test Odoo against the live database ==")
    response = owner.post(f"/tenants/{tenant_id}/test-odoo", timeout=180.0)
    location = response.headers.get("location", "")
    check("Test Odoo reported success", "error=" not in location, location[:200])

    print("\n== Open in Odoo hands the browser a session ==")
    response = owner.get(f"/tenants/{tenant_id}/open", timeout=180.0)
    cookie = response.headers.get("set-cookie", "")
    location = response.headers.get("location", "")
    check("open redirects to Odoo", "://" in location and "/web" in location, location)
    check("open sets a session_id cookie", "session_id=" in cookie, cookie[:120])


def main() -> int:
    print(f"manager database: {settings.manager_db_url.split('@')[-1]}")
    reset_test_data()
    check_permission_matrix()
    check_cookie_domain_rules()
    owner = check_owner_sections()
    check_account_creation(owner)
    check_role_enforcement()
    check_self_protection(owner)
    check_tenant_and_odoo(owner)

    print()
    total = _passed + len(_failed)
    if _failed:
        print(f"{len(_failed)} of {total} checks FAILED:")
        for label in _failed:
            print(f"  - {label}")
        return 1
    print(f"ALL {total} CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
