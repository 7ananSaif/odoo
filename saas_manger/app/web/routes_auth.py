"""Login, logout and 2FA enrolment.

NOTE: this module deliberately does NOT use ``from __future__ import
annotations``. The handlers below are wrapped by ``@limiter.limit(...)``, and
with postponed (string) annotations FastAPI resolves them against slowapi's
module globals, where ``SessionDep`` does not exist — the dependency then
degrades into a required *query* parameter and every login returns HTTP 422.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.deps import SessionDep, client_ip
from app.models.user import User
from app.security import (
    create_session_token,
    decrypt_secret,
    encrypt_secret,
    generate_totp_secret,
    load_session_token,
    totp_qr_png_base64,
    verify_password,
    verify_totp,
)
from app.services import audit
from app.web.ratelimit import limiter
from app.web.templating import render

router = APIRouter(tags=["auth"])

MAX_FAILED = 5
LOCK_MINUTES = 15


def _set_session(response: RedirectResponse, user: User) -> None:
    token = create_session_token(user.id, user.email)
    response.set_cookie(
        settings.session_cookie,
        token,
        max_age=settings.session_max_age_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.odoo_base_url.startswith("https"),
    )


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, session: SessionDep, next: str = "/"):
    """Show the login page (step 1: email + password)."""
    if load_session_token(request.cookies.get(settings.session_cookie, "")):
        return RedirectResponse(next or "/", status_code=status.HTTP_303_SEE_OTHER)
    return render(request, "login.html", {"next": next, "step": "password"})


@router.post("/login")
@limiter.limit(settings.rate_limit_login)
def login_submit(
    request: Request,
    session: SessionDep,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    """Verify credentials, then either enrol/ask for TOTP or open the session."""
    user = session.query(User).filter(User.email == email.strip().lower()).one_or_none()

    if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        return render(request, "login.html", {
            "step": "password", "next": next,
            "error": "Account temporarily locked. Try again later.",
        }, status_code=401)

    if user is None or not verify_password(password, user.password_hash):
        if user is not None:
            user.failed_logins = (user.failed_logins or 0) + 1
            if user.failed_logins >= MAX_FAILED:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCK_MINUTES)
            session.commit()
        audit.record(session, action="auth.login_failed", actor=email, level="warning",
                     ip=client_ip(request), detail="bad credentials")
        session.commit()
        return render(request, "login.html", {
            "step": "password", "next": next, "error": "Invalid email or password.",
        }, status_code=401)

    # First login: enrol TOTP. Reuse an existing pending secret when present so
    # that refreshing the login page (or resubmitting the password step) does
    # not silently rotate the secret and invalidate a QR the user already
    # scanned — which showed up as a permanent "Invalid code".
    if not user.totp_enabled:
        secret = decrypt_secret(user.totp_secret_enc) or generate_totp_secret()
        user.totp_secret_enc = encrypt_secret(secret)
        session.commit()
        return render(request, "login.html", {
            "step": "enroll", "next": next, "email": user.email,
            "qr": totp_qr_png_base64(secret, user.email), "secret": secret,
        })

    return render(request, "login.html", {
        "step": "totp", "next": next, "email": user.email,
    })


@router.post("/login/totp")
@limiter.limit(settings.rate_limit_login)
def login_totp(
    request: Request,
    session: SessionDep,
    email: str = Form(...),
    code: str = Form(...),
    next: str = Form("/"),
):
    """Second step: verify the TOTP code (also confirms enrolment)."""
    user = session.query(User).filter(User.email == email.strip().lower()).one_or_none()
    if user is None:
        return render(request, "login.html", {"step": "password", "next": next, "error": "Unknown user."}, status_code=401)

    secret = decrypt_secret(user.totp_secret_enc) or ""
    if not verify_totp(secret, code):
        audit.record(session, action="auth.2fa_failed", actor=email, level="warning",
                     ip=client_ip(request), detail="bad totp")
        session.commit()
        step = "totp" if user.totp_enabled else "enroll"
        extra = {} if user.totp_enabled else {"qr": totp_qr_png_base64(secret, user.email), "secret": secret}
        return render(request, "login.html", {
            "step": step, "next": next, "email": user.email, "error": "Invalid code.", **extra,
        }, status_code=401)

    user.totp_enabled = True
    user.last_login_at = datetime.now(timezone.utc)
    user.failed_logins = 0
    user.locked_until = None
    session.commit()

    audit.record(session, action="auth.login", actor=user.email, ip=client_ip(request))
    session.commit()

    response = RedirectResponse(next or "/", status_code=status.HTTP_303_SEE_OTHER)
    _set_session(response, user)
    return response


@router.get("/logout")
def logout(request: Request):
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.session_cookie)
    return response
