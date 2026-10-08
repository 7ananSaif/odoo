"""Role-based permissions for manager users (owner > admin > operator > viewer).

Role semantics
--------------
owner
    Full control, including user management and settings.
admin
    Everything an operator can do, plus plan and finance administration, but
    *not* user management or settings.
operator
    Day-to-day tenant work: create/edit tenants, push limits, backups, updates.
viewer
    Read-only access to tenants, plans, finance and the audit log.

Permissions are plain string keys ("tenants.manage").  The helpers here are
model-agnostic on purpose: they accept anything carrying a ``role`` attribute
(or a bare role string), so this module never imports ``app.models.user`` —
``app.models.user`` and the web layer are free to import *us*, and no import
cycle can form.

This module deliberately avoids ``from __future__ import annotations``: the
``require_permission`` factory returns a FastAPI dependency, and FastAPI must
see real objects rather than postponed annotation strings.  See the note at the
top of ``app/web/routes_auth.py`` for the failure that postponed annotations
cause in FastAPI signatures.
"""

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"

# Strongest first.  The index doubles as the privilege rank (lower = stronger),
# which is what ``can_assign_role`` compares.
ROLES: tuple = (ROLE_OWNER, ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER)

ROLE_LABELS: dict = {
    ROLE_OWNER: "Owner",
    ROLE_ADMIN: "Admin",
    ROLE_OPERATOR: "Operator",
    ROLE_VIEWER: "Viewer",
}

ROLE_DESCRIPTIONS: dict = {
    ROLE_OWNER: "Full control: users, settings, tenants, plans, finance and operations.",
    ROLE_ADMIN: "Everything except user management and settings.",
    ROLE_OPERATOR: "Day-to-day tenant work: create/edit, push limits, backups and updates.",
    ROLE_VIEWER: "Read-only access to tenants, plans, finance and the audit log.",
}

# ---------------------------------------------------------------------------
# Permission keys
# ---------------------------------------------------------------------------
PERM_USERS_VIEW = "users.view"
PERM_USERS_MANAGE = "users.manage"
PERM_SETTINGS_MANAGE = "settings.manage"
PERM_TENANTS_VIEW = "tenants.view"
PERM_TENANTS_MANAGE = "tenants.manage"
PERM_TENANTS_DELETE = "tenants.delete"
PERM_PLANS_VIEW = "plans.view"
PERM_PLANS_MANAGE = "plans.manage"
PERM_FINANCE_VIEW = "finance.view"
PERM_FINANCE_MANAGE = "finance.manage"
PERM_BACKUPS_MANAGE = "backups.manage"
PERM_UPDATES_MANAGE = "updates.manage"
PERM_AUDIT_VIEW = "audit.view"
PERM_APPS_VIEW = "apps.view"
PERM_APPS_MANAGE = "apps.manage"

ALL_PERMISSIONS: tuple = (
    PERM_USERS_VIEW,
    PERM_USERS_MANAGE,
    PERM_SETTINGS_MANAGE,
    PERM_TENANTS_VIEW,
    PERM_TENANTS_MANAGE,
    PERM_TENANTS_DELETE,
    PERM_PLANS_VIEW,
    PERM_PLANS_MANAGE,
    PERM_FINANCE_VIEW,
    PERM_FINANCE_MANAGE,
    PERM_BACKUPS_MANAGE,
    PERM_UPDATES_MANAGE,
    PERM_AUDIT_VIEW,
    PERM_APPS_VIEW,
    PERM_APPS_MANAGE,
)

PERMISSION_LABELS: dict = {
    PERM_USERS_VIEW: "View users",
    PERM_USERS_MANAGE: "Add, edit and remove users",
    PERM_SETTINGS_MANAGE: "Change settings",
    PERM_TENANTS_VIEW: "View tenants",
    PERM_TENANTS_MANAGE: "Create and edit tenants, push limits",
    PERM_TENANTS_DELETE: "Delete tenants and drop databases",
    PERM_PLANS_VIEW: "View plans",
    PERM_PLANS_MANAGE: "Create and edit plans",
    PERM_FINANCE_VIEW: "View invoices and balances",
    PERM_FINANCE_MANAGE: "Record payments, deposits and refunds",
    PERM_BACKUPS_MANAGE: "Create and restore backups",
    PERM_UPDATES_MANAGE: "Run module/app updates",
    PERM_AUDIT_VIEW: "Read the audit log",
    PERM_APPS_VIEW: "View the stack's application containers",
    PERM_APPS_MANAGE: "Start, stop and restart application containers",
}

_OPERATOR_PERMISSIONS = frozenset({
    PERM_TENANTS_VIEW,
    PERM_TENANTS_MANAGE,
    PERM_PLANS_VIEW,
    PERM_FINANCE_VIEW,
    PERM_BACKUPS_MANAGE,
    PERM_UPDATES_MANAGE,
    PERM_AUDIT_VIEW,
    PERM_APPS_VIEW,
})

_VIEWER_PERMISSIONS = frozenset({
    PERM_TENANTS_VIEW,
    PERM_PLANS_VIEW,
    PERM_FINANCE_VIEW,
    PERM_AUDIT_VIEW,
    PERM_APPS_VIEW,
})

_ADMIN_PERMISSIONS = _OPERATOR_PERMISSIONS | frozenset({
    PERM_TENANTS_DELETE,
    PERM_PLANS_MANAGE,
    PERM_FINANCE_MANAGE,
    PERM_APPS_MANAGE,
})

ROLE_PERMISSIONS: dict = {
    ROLE_OWNER: frozenset(ALL_PERMISSIONS),
    ROLE_ADMIN: _ADMIN_PERMISSIONS,
    ROLE_OPERATOR: _OPERATOR_PERMISSIONS,
    ROLE_VIEWER: _VIEWER_PERMISSIONS,
}

# Role → permission keys, ordered for display in the "what can this role do"
# table on the users screens.
ROLE_PERMISSION_LIST: dict = {
    role: tuple(p for p in ALL_PERMISSIONS if p in ROLE_PERMISSIONS[role])
    for role in ROLES
}


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
def normalize_role(role) -> str:
    """Return a known role.  Anything unknown degrades to ``viewer`` (safe)."""
    if not role:
        return ROLE_VIEWER
    value = str(role).strip().lower()
    return value if value in ROLE_PERMISSIONS else ROLE_VIEWER


def role_label(role) -> str:
    """Human label for a role value."""
    return ROLE_LABELS.get(normalize_role(role), ROLE_LABELS[ROLE_VIEWER])


def permission_label(permission: str) -> str:
    """Human label for a permission key."""
    return PERMISSION_LABELS.get(permission, permission)


def is_valid_role(role) -> bool:
    """True when ``role`` names one of the four supported roles."""
    return bool(role) and str(role).strip().lower() in ROLE_PERMISSIONS


def _role_of(subject) -> str:
    """Resolve the role of a User instance, a role string, or ``None``.

    Rows created before the ``role`` column existed fall back to the legacy
    ``is_superuser`` flag: superusers become owners, everyone else a viewer.
    """
    if subject is None:
        return ROLE_VIEWER
    if isinstance(subject, str):
        return normalize_role(subject)
    role = getattr(subject, "role", None)
    if role:
        return normalize_role(role)
    return ROLE_OWNER if getattr(subject, "is_superuser", False) else ROLE_VIEWER


def permissions_for(subject) -> frozenset:
    """Return the set of permission keys granted to ``subject``."""
    return ROLE_PERMISSIONS[_role_of(subject)]


def has_permission(subject, permission) -> bool:
    """True when ``subject`` holds ``permission`` (and is an active account)."""
    if subject is None:
        return False
    if getattr(subject, "is_active", True) is False:
        return False
    return permission in permissions_for(subject)


def can_assign_role(actor, role) -> bool:
    """True when ``actor`` may create/assign an account the given ``role``.

    Assigning a role requires ``users.manage`` and the target role must not be
    stronger than the actor's own role (an admin cannot mint an owner).  Only
    owners hold ``users.manage`` today, so in practice owners manage users.
    """
    if not has_permission(actor, PERM_USERS_MANAGE):
        return False
    if not is_valid_role(role):
        return False
    actor_role = _role_of(actor)
    return ROLES.index(normalize_role(role)) >= ROLES.index(actor_role)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def require_permission(permission: str):
    """Return a FastAPI dependency that enforces ``permission``.

    Usage::

        @router.get("")
        def list_view(user: User = Depends(require_permission(PERM_USERS_VIEW))):
            ...

    The dependency resolves the logged-in user through ``app.deps.require_user``
    (which redirects anonymous visitors to ``/login``) and raises HTTP 403 when
    the role does not grant the permission.  ``app.deps`` is imported lazily so
    this module keeps zero import-time dependencies on the web layer.
    """
    from fastapi import Depends, HTTPException, status

    from app.deps import require_user

    def dependency(user=Depends(require_user)):
        if not has_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Your role ({role_label(getattr(user, 'role', None))}) "
                    f"is not allowed to {permission_label(permission).lower()}."
                ),
            )
        return user

    dependency.__name__ = f"require_permission_{permission.replace('.', '_')}"
    return dependency


def require_permission_for_write(view_permission: str, manage_permission: str):
    """Return a dependency that reads with ``view_permission`` and writes with ``manage_permission``.

    ``GET``, ``HEAD`` and ``OPTIONS`` need only the view permission; every other
    method needs the manage permission.  Applied at the router level (see
    :mod:`app.main`) it lets a read-only role browse a section while blocking
    every change to it.
    """
    from fastapi import Depends, HTTPException, Request, status

    from app.deps import require_user

    read_methods = frozenset({"GET", "HEAD", "OPTIONS"})

    def dependency(request: Request, user=Depends(require_user)):
        required = view_permission if request.method in read_methods else manage_permission
        if not has_permission(user, required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Your role ({role_label(getattr(user, 'role', None))}) "
                    f"is not allowed to {permission_label(required).lower()}."
                ),
            )
        return user

    dependency.__name__ = f"require_write_{manage_permission.replace('.', '_')}"
    return dependency


__all__ = [
    "ALL_PERMISSIONS",
    "PERMISSION_LABELS",
    "ROLES",
    "ROLE_ADMIN",
    "ROLE_DESCRIPTIONS",
    "ROLE_LABELS",
    "ROLE_OPERATOR",
    "ROLE_OWNER",
    "ROLE_PERMISSIONS",
    "ROLE_PERMISSION_LIST",
    "ROLE_VIEWER",
    "can_assign_role",
    "has_permission",
    "is_valid_role",
    "normalize_role",
    "permission_label",
    "permissions_for",
    "require_permission",
    "require_permission_for_write",
    "role_label",
]
