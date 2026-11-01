"""Users: add, edit, disable and delete manager operator accounts.

Access is role-gated (see :mod:`app.services.permissions`): listing needs
``users.view``, every mutation needs ``users.manage``.  Only the *owner* role
holds ``users.manage`` today, so owners administer accounts and nobody else.

Safety rails enforced here so the panel can never lock itself out:

* an account may not delete or deactivate itself;
* the last *active owner* can neither lose the owner role, be deactivated nor
  be deleted — promote or create another owner first.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from app.deps import SessionDep, client_ip
from app.models.user import User
from app.security import hash_password
from app.services import audit, permissions
from app.web.templating import render

router = APIRouter(prefix="/users", tags=["users"])

MIN_PASSWORD_LENGTH = 8

require_view = permissions.require_permission(permissions.PERM_USERS_VIEW)
require_manage = permissions.require_permission(permissions.PERM_USERS_MANAGE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _redirect(url: str, flash: str = "", error: str = "") -> RedirectResponse:
    from urllib.parse import urlencode  # noqa: PLC0415

    params = {}
    if flash:
        params["flash"] = flash
    if error:
        params["error"] = error
    suffix = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{url}{suffix}", status_code=303)


def _normalized_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _is_valid_email(email: str) -> bool:
    return bool(email) and "@" in email and " " not in email


def _active_owner_count(session, exclude_id: int | None = None) -> int:
    """Number of active owners, optionally ignoring one account id."""
    stmt = select(func.count(User.id)).where(
        User.role == permissions.ROLE_OWNER, User.is_active.is_(True)
    )
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    return int(session.scalar(stmt) or 0)


def _is_last_active_owner(session, account: User) -> bool:
    """True when ``account`` is the only active owner left."""
    if permissions.normalize_role(account.role) != permissions.ROLE_OWNER or not account.is_active:
        return False
    return _active_owner_count(session, exclude_id=account.id) == 0


def _assignable_roles(actor: User) -> list[dict]:
    """Roles ``actor`` may hand out: never stronger than their own."""
    actor_rank = permissions.ROLES.index(permissions.normalize_role(actor.role))
    return [
        {
            "value": role,
            "label": permissions.ROLE_LABELS[role],
            "description": permissions.ROLE_DESCRIPTIONS[role],
        }
        for role in permissions.ROLES
        if permissions.ROLES.index(role) >= actor_rank
    ]


def _role_matrix() -> list[dict]:
    """Role → capability rows shown under the user list."""
    return [
        {
            "role": role,
            "label": permissions.ROLE_LABELS[role],
            "description": permissions.ROLE_DESCRIPTIONS[role],
            "permissions": [
                permissions.permission_label(key)
                for key in permissions.ROLE_PERMISSION_LIST[role]
            ],
        }
        for role in permissions.ROLES
    ]


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@router.get("", response_class=HTMLResponse)
def list_view(request: Request, session: SessionDep, user: User = Depends(require_view)):
    accounts = list(
        session.scalars(select(User).order_by(User.role, User.email)).all()
    )
    return render(request, "users/list.html", {
        "accounts": accounts,
        "role_matrix": _role_matrix(),
        "current_user_id": user.id,
        "can_manage": permissions.has_permission(user, permissions.PERM_USERS_MANAGE),
    })


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
@router.get("/new", response_class=HTMLResponse)
def new_form(request: Request, session: SessionDep, user: User = Depends(require_manage)):
    return render(request, "users/form.html", {
        "account": None,
        "assignable_roles": _assignable_roles(user),
        "min_password": MIN_PASSWORD_LENGTH,
        "is_self": False,
        "is_last_active_owner": False,
    })


@router.post("/new")
def create(
    request: Request,
    session: SessionDep,
    user: User = Depends(require_manage),
    email: str = Form(...),
    name: str = Form(""),
    role: str = Form(permissions.ROLE_VIEWER),
    password: str = Form(...),
    password_confirm: str = Form(""),
):
    email = _normalized_email(email)
    if not _is_valid_email(email):
        return _redirect("/users/new", error="Enter a valid email address")
    if session.scalar(select(User).where(User.email == email)):
        return _redirect("/users/new", error="That email is already registered")
    if len(password) < MIN_PASSWORD_LENGTH:
        return _redirect("/users/new", error=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if password_confirm and password_confirm != password:
        return _redirect("/users/new", error="Passwords do not match")
    if not permissions.can_assign_role(user, role):
        return _redirect("/users/new", error="You are not allowed to assign that role")

    account = User(
        email=email,
        name=name.strip() or email.split("@")[0],
        password_hash=hash_password(password),
    )
    account.apply_role(role)
    session.add(account)
    audit.record(
        session, action="user.create", actor=user.email, target_type="user",
        target_id=account.id, ip=client_ip(request),
        detail=f"{email} role={permissions.normalize_role(role)}",
    )
    session.commit()
    return _redirect("/users", flash=f"User {email} created as {permissions.role_label(role)}")


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------
@router.get("/{user_id}/edit", response_class=HTMLResponse)
def edit_form(request: Request, session: SessionDep, user_id: int,
              user: User = Depends(require_manage)):
    account = session.get(User, user_id)
    if account is None:
        raise HTTPException(404, "User not found")
    return render(request, "users/form.html", {
        "account": account,
        "assignable_roles": _assignable_roles(user),
        "min_password": MIN_PASSWORD_LENGTH,
        "is_self": account.id == user.id,
        "is_last_active_owner": _is_last_active_owner(session, account),
    })


@router.post("/{user_id}/edit")
def update(
    request: Request,
    session: SessionDep,
    user_id: int,
    user: User = Depends(require_manage),
    email: str = Form(...),
    name: str = Form(""),
    role: str = Form(permissions.ROLE_VIEWER),
    is_active: bool = Form(False),
    password: str = Form(""),
):
    account = session.get(User, user_id)
    if account is None:
        raise HTTPException(404, "User not found")

    target = f"/users/{user_id}/edit"
    email = _normalized_email(email)
    if not _is_valid_email(email):
        return _redirect(target, error="Enter a valid email address")
    clash = session.scalar(select(User).where(User.email == email, User.id != user_id))
    if clash is not None:
        return _redirect(target, error="That email is already registered")

    new_role = permissions.normalize_role(role)
    if new_role != permissions.normalize_role(account.role) and not permissions.can_assign_role(user, role):
        return _redirect(target, error="You are not allowed to assign that role")

    if account.id == user.id and not is_active:
        return _redirect(target, error="You cannot deactivate your own account")

    demotes_owner = (
        permissions.normalize_role(account.role) == permissions.ROLE_OWNER
        and (new_role != permissions.ROLE_OWNER or not is_active)
    )
    if demotes_owner and _is_last_active_owner(session, account):
        return _redirect(target, error="This is the last active owner — promote another owner first")

    if password and len(password) < MIN_PASSWORD_LENGTH:
        return _redirect(target, error=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")

    account.email = email
    account.name = name.strip() or account.name
    account.apply_role(role)
    account.is_active = is_active
    if password:
        account.password_hash = hash_password(password)
        account.failed_logins = 0
        account.locked_until = None

    detail = f"{email} role={new_role} active={is_active}"
    if password:
        detail += " password_reset=1"
    audit.record(
        session, action="user.update", actor=user.email, target_type="user",
        target_id=account.id, ip=client_ip(request), detail=detail,
    )
    session.commit()
    return _redirect("/users", flash=f"User {email} updated")


@router.post("/{user_id}/toggle-active")
def toggle_active(request: Request, session: SessionDep, user_id: int,
                  user: User = Depends(require_manage)):
    account = session.get(User, user_id)
    if account is None:
        raise HTTPException(404, "User not found")
    if account.id == user.id:
        return _redirect("/users", error="You cannot deactivate your own account")
    if account.is_active and _is_last_active_owner(session, account):
        return _redirect("/users", error="Cannot deactivate the last active owner")

    account.is_active = not account.is_active
    audit.record(
        session, action="user.toggle_active", actor=user.email, target_type="user",
        target_id=account.id, ip=client_ip(request),
        detail=f"{account.email} active={account.is_active}",
    )
    session.commit()
    state = "activated" if account.is_active else "deactivated"
    return _redirect("/users", flash=f"User {account.email} {state}")


@router.post("/{user_id}/reset-2fa")
def reset_2fa(request: Request, session: SessionDep, user_id: int,
              user: User = Depends(require_manage)):
    account = session.get(User, user_id)
    if account is None:
        raise HTTPException(404, "User not found")
    account.totp_secret_enc = None
    account.totp_enabled = False
    audit.record(
        session, action="user.reset_2fa", actor=user.email, target_type="user",
        target_id=account.id, ip=client_ip(request), level="warning", detail=account.email,
    )
    session.commit()
    return _redirect(
        "/users",
        flash=f"2FA reset for {account.email} — it is re-enrolled on their next sign-in",
    )


@router.post("/{user_id}/delete")
def delete(request: Request, session: SessionDep, user_id: int,
           user: User = Depends(require_manage)):
    account = session.get(User, user_id)
    if account is None:
        raise HTTPException(404, "User not found")
    if account.id == user.id:
        return _redirect("/users", error="You cannot delete your own account")
    if _is_last_active_owner(session, account):
        return _redirect("/users", error="Cannot delete the last active owner")

    email = account.email
    audit.record(
        session, action="user.delete", actor=user.email, target_type="user",
        target_id=account.id, ip=client_ip(request), level="warning", detail=email,
    )
    session.delete(account)
    session.commit()
    return _redirect("/users", flash=f"User {email} deleted")
