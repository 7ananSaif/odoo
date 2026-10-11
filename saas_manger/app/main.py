"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import __version__
from app.config import settings
from app.deps import get_current_user
from app.db import SessionLocal
from app.services import permissions
from app.web.ratelimit import limiter
from app.web.routes_audit import router as audit_router
from app.web.routes_auth import router as auth_router
from app.web.routes_dashboard import router as dashboard_router
from app.web.routes_finance import router as finance_router
from app.web.routes_plans import router as plans_router
from app.web.routes_settings import router as settings_router
from app.web.routes_tenants import router as tenants_router
from app.web.routes_updates import router as updates_router
from app.web.routes_users import router as users_router
from app.web.templating import TEMPLATES_DIR
from app.web.templating import render as render_template

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
_logger = logging.getLogger("saas_manager")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown. Seeds settings and warns about missing config."""
    if not settings.secrets_key or settings.secrets_key.startswith("change-me"):
        _logger.warning("SECRETS_KEY is not set — encrypted secrets will not work. See .env.example")
    if not settings.odoo_manager_token or settings.odoo_manager_token.startswith("change-me"):
        _logger.warning("ODOO_MANAGER_TOKEN is not set — the Odoo lock cannot be bypassed. See .env.example")
    with SessionLocal() as session:
        from app.services import settings_service  # noqa: PLC0415

        settings_service.seed_defaults(session)
        session.commit()
    _logger.info("SaaS Manager %s started", __version__)
    yield
    _logger.info("SaaS Manager stopped")


app = FastAPI(
    title="SaaS Manager",
    version=__version__,
    description="Standalone manager for multi-tenant Odoo.",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse({"detail": "Too many requests. Please slow down."}, status_code=429)


@app.middleware("http")
async def load_user_middleware(request: Request, call_next):
    """Attach the current user to ``request.state`` so templates can use it."""
    request.state.user = None
    token = request.cookies.get(settings.session_cookie)
    if token:
        with SessionLocal() as session:
            try:
                request.state.user = get_current_user(request, session)
            except Exception:  # noqa: BLE001
                request.state.user = None
    return await call_next(request)


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Every router except authentication is gated by the role matrix in
# app.services.permissions.  Router-level dependencies cover *seeing* a
# section (a viewer can read tenants; an operator cannot open Settings), and
# the mutating handlers in each router add a second "manage" guard on top.
app.include_router(auth_router)
app.include_router(
    dashboard_router,
    dependencies=[Depends(permissions.require_permission(permissions.PERM_TENANTS_VIEW))],
)
app.include_router(
    tenants_router,
    dependencies=[Depends(permissions.require_permission(permissions.PERM_TENANTS_VIEW))],
)
app.include_router(
    plans_router,
    dependencies=[Depends(permissions.require_permission(permissions.PERM_PLANS_VIEW))],
)
app.include_router(
    updates_router,
    dependencies=[Depends(permissions.require_permission(permissions.PERM_UPDATES_MANAGE))],
)
app.include_router(
    finance_router,
    # Reads need finance.view; any write (payments, deposits, refunds, credit
    # notes, invoice actions) needs finance.manage.
    dependencies=[Depends(permissions.require_permission_for_write(
        permissions.PERM_FINANCE_VIEW, permissions.PERM_FINANCE_MANAGE))],
)
app.include_router(
    settings_router,
    dependencies=[Depends(permissions.require_permission(permissions.PERM_SETTINGS_MANAGE))],
)
app.include_router(
    audit_router,
    dependencies=[Depends(permissions.require_permission(permissions.PERM_AUDIT_VIEW))],
)
app.include_router(users_router)


@app.get("/health", response_class=JSONResponse)
def health() -> dict:
    """Liveness probe used by the service installer and monitoring."""
    return {
        "status": "ok",
        "version": __version__,
        "configured": settings.is_configured,
    }


@app.exception_handler(404)
async def not_found(request: Request, exc):
    if request.url.path.startswith(("/static", "/health")):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return render_template(request, "error.html", {
        "code": 404, "message": "Page not found",
    }, status_code=404)


@app.exception_handler(403)
async def forbidden(request: Request, exc):
    """Render a friendly page when a role lacks a permission (the RBAC guard)."""
    detail = getattr(exc, "detail", None) or "You are not allowed to do that."
    if request.url.path.startswith(("/static", "/health")):
        return JSONResponse({"detail": detail}, status_code=403)
    return render_template(request, "error.html", {
        "code": 403, "message": detail,
    }, status_code=403)


@app.exception_handler(500)
async def server_error(request: Request, exc):
    return render_template(request, "error.html", {
        "code": 500, "message": "Something went wrong",
    }, status_code=500)
