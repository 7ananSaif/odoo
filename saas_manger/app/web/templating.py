"""Jinja2 environment, filters and the shared render helper."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import __version__
from app.config import settings
from app.models.enums import TenantStatus

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- Filters ----------------------------------------------------------------
def money_filter(value: Decimal | float | int | str | None, currency: str = "") -> str:
    """Format a decimal as ``1,234.56 CUR``."""
    try:
        amount = Decimal(str(value or 0))
    except Exception:  # noqa: BLE001
        amount = Decimal("0")
    text = f"{amount:,.2f}"
    return f"{text} {currency}".strip()


def datetime_filter(value: datetime | date | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    if not value:
        return "—"
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return value.strftime(fmt)


def date_filter(value: datetime | date | None) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return value.strftime("%Y-%m-%d")


def status_color(value: str | None) -> str:
    """Return a Tailwind-ish badge colour name for a status."""
    return {
        "trial": "info",
        "active": "success",
        "past_due": "warning",
        "suspended": "danger",
        "expired": "danger",
        "cancelled": "muted",
        "draft": "muted",
        "sent": "info",
        "paid": "success",
        "overdue": "danger",
        "pending": "muted",
        "running": "info",
        "success": "success",
        "failed": "danger",
        "partial": "warning",
    }.get((value or "").lower(), "muted")


templates.env.filters["money"] = money_filter
templates.env.filters["dt"] = datetime_filter
templates.env.filters["date"] = date_filter
templates.env.filters["status_color"] = status_color
templates.env.globals["app_version"] = __version__
templates.env.globals["tenant_statuses"] = [s.value for s in TenantStatus]


def render(request: Request, template: str, context: dict[str, Any] | None = None, *, status_code: int = 200):
    """Render a template with the shared context (user, settings, flash message)."""
    data: dict[str, Any] = {
        "request": request,
        "user": getattr(request.state, "user", None),
        "settings": settings,
        "app_name": "SaaS Manager",
    }
    data.update(context or {})
    # Per-request permission probe so templates can hide what the role cannot
    # do:  {% if can('users.view') %}.  Bound to *this* request's user.
    from app.services import permissions as permissions_service  # noqa: PLC0415

    current_user = data.get("user")
    data["can"] = lambda permission: permissions_service.has_permission(current_user, permission)
    # Query-string flash/error support the redirect pattern (?error=...), but an
    # explicit value passed in the context must win — otherwise every handler
    # that renders its own error message has it silently wiped.
    data.setdefault("flash", request.query_params.get("flash", ""))
    data.setdefault("error", request.query_params.get("error", ""))
    return templates.TemplateResponse(request, template, data, status_code=status_code)
