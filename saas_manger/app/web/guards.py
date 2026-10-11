"""In-handler permission helpers shared by the route modules.

Router-level dependencies in :mod:`app.main` gate *seeing* a section; the
helpers here gate the *mutating* handlers inside it.  They return a plain error
message (or ``""`` when allowed) so each router can reuse its own ``_redirect``
and keep the flash/error wording consistent with the rest of the page.
"""
from __future__ import annotations

from app.services import permissions


def permission_error(user, permission: str, action: str) -> str:
    """Return an error message when ``user`` may not ``permission``, else ``""``.

    ``action`` reads as a verb phrase, e.g. ``"create plans"``, producing
    "Your role (Viewer) cannot create plans."
    """
    if permissions.has_permission(user, permission):
        return ""
    role = permissions.role_label(getattr(user, "role", None))
    return f"Your role ({role}) cannot {action}."
