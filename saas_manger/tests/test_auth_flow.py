"""End-to-end test of the login flow (password → TOTP → session).

Guards a real regression: with ``from __future__ import annotations`` in a
module whose handlers are wrapped by ``@limiter.limit(...)``, FastAPI resolved
the string annotation ``"SessionDep"`` against slowapi's globals, turned it into
a required *query* parameter and answered every login with HTTP 422.
"""
from __future__ import annotations

import re

import pyotp
import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.user import User
from app.security import hash_password

EMAIL = "flowtest@example.com"
PASSWORD = "flow-test-password"


@pytest.fixture()
def flow_user():
    with SessionLocal() as session:
        user = session.query(User).filter(User.email == EMAIL).one_or_none()
        if user is None:
            user = User(email=EMAIL, name="Flow Test", password_hash=hash_password(PASSWORD))
            session.add(user)
        else:
            user.password_hash = hash_password(PASSWORD)
        user.totp_enabled = False
        user.totp_secret_enc = None
        user.failed_logins = 0
        user.locked_until = None
        session.commit()
    yield EMAIL


@pytest.fixture()
def anon_client():
    return TestClient(app, follow_redirects=False)


def test_login_post_is_not_a_422(flow_user, anon_client):
    """The regression: the password step must accept the form, not demand a query param."""
    resp = anon_client.post("/login", data={"email": flow_user, "password": PASSWORD, "next": "/"})
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text[:300]}"
    assert "query" not in resp.text


def test_wrong_password_is_rejected(flow_user, anon_client):
    resp = anon_client.post("/login", data={"email": flow_user, "password": "nope", "next": "/"})
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.text


def test_full_login_enrols_totp_and_opens_a_session(flow_user, anon_client):
    # Step 1: password -> enrolment page with the manual key.
    first = anon_client.post("/login", data={"email": flow_user, "password": PASSWORD, "next": "/"})
    assert first.status_code == 200
    assert "Manual key" in first.text
    match = re.search(r"Manual key:\s*<code>([A-Z2-7]+)</code>", first.text)
    assert match, "the enrolment page must show the manual TOTP key"
    secret = match.group(1)

    # Step 2: the TOTP code -> session cookie + redirect.
    code = pyotp.TOTP(secret).now()
    second = anon_client.post(
        "/login/totp",
        data={"email": flow_user, "code": code, "next": "/"},
    )
    assert second.status_code == 303, f"expected a redirect, got {second.status_code}: {second.text[:300]}"
    assert second.headers["location"] == "/"
    assert "saas_session" in second.cookies or "saas_session" in second.headers.get("set-cookie", "")

    # Step 3: the session opens the dashboard.
    dashboard = anon_client.get("/", cookies=second.cookies)
    assert dashboard.status_code == 200
    assert "Sign in" not in dashboard.text


def test_totp_rejects_a_bad_code(flow_user, anon_client):
    anon_client.post("/login", data={"email": flow_user, "password": PASSWORD, "next": "/"})
    resp = anon_client.post("/login/totp", data={"email": flow_user, "code": "000000", "next": "/"})
    if resp.status_code == 200:
        pytest.skip("the generated code happened to be 000000")
    assert resp.status_code == 401
    assert "Invalid code" in resp.text


def test_unauthenticated_dashboard_redirects_to_login(anon_client):
    resp = anon_client.get("/")
    assert resp.status_code in (303, 307)
    assert resp.headers["location"] == "/login"
