"""Containers: start, stop and restart the stack's application containers.

The panel is a thin, guarded wrapper around
:mod:`app.services.docker_control`. Listing needs ``containers.view`` (enforced
at the router in :mod:`app.main`); every action needs ``containers.manage`` and
is checked again in the handlers below, so a read-only role can watch the stack
but never touch it.

What may be controlled is decided by configuration, not by this module: the
``APP_SERVICES`` allowlist (minus ``PROTECTED_SERVICES``) in
``app/services/docker_control.py``. Every action is written to the audit log.

This screen is *not* about a tenant's Odoo apps — that is the Apps screen, see
:mod:`app.web.routes_apps`.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.deps import CurrentUser, SessionDep, client_ip
from app.services import audit, docker_control, permissions
from app.web import guards
from app.web.templating import render

router = APIRouter(prefix="/containers", tags=["containers"])

#: Past tense for the flash messages ("start" → "started").
_PAST_TENSE = {"start": "started", "stop": "stopped", "restart": "restarted"}


def _redirect(url: str, flash: str = "", error: str = "") -> RedirectResponse:
    from urllib.parse import urlencode  # noqa: PLC0415

    params = {}
    if flash:
        params["flash"] = flash
    if error:
        params["error"] = error
    suffix = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{url}{suffix}", status_code=303)


def _manage_error(user) -> str:
    """The error to show when ``user`` may not touch containers, else ``""``."""
    return guards.permission_error(user, permissions.PERM_CONTAINERS_MANAGE, "control containers")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@router.get("", response_class=HTMLResponse)
def list_view(request: Request, session: SessionDep, user: CurrentUser):
    """Show every controllable app container and its current state."""
    available = docker_control.socket_available()
    apps = []
    docker_error = ""
    if available:
        try:
            apps = docker_control.list_apps()
        except docker_control.DockerError as exc:
            docker_error = str(exc)
    return render(request, "containers/list.html", {
        "apps": apps,
        "docker_available": available,
        "docker_socket": settings.docker_socket,
        "allowlist": docker_control.allowlist(),
        "protected_services": sorted(docker_control.PROTECTED_SERVICES),
        "can_control": permissions.has_permission(user, permissions.PERM_CONTAINERS_MANAGE),
        "error": docker_error,
    })


# ---------------------------------------------------------------------------
# One container
# ---------------------------------------------------------------------------
@router.post("/{service}/{action}")
def control_one(request: Request, session: SessionDep, user: CurrentUser,
                service: str, action: str):
    """Start, stop or restart a single app container."""
    if error := _manage_error(user):
        return _redirect("/containers", error=error)
    try:
        app = docker_control.control(service, action)
    except docker_control.DockerError as exc:
        audit.record(session, action=f"containers.{action}", actor=user.email,
                     target_type="container", target_id=service, ip=client_ip(request),
                     level="error", detail=str(exc))
        session.commit()
        return _redirect("/containers", error=f"Could not {action} {service}: {exc}")

    state = app.state_label if app else "unknown"
    audit.record(session, action=f"containers.{action}", actor=user.email,
                 target_type="container", target_id=service, ip=client_ip(request),
                 level="warning", detail=f"{service} -> {state}")
    session.commit()
    return _redirect("/containers", flash=f"{service} {_PAST_TENSE.get(action, action)} ({state})")


# ---------------------------------------------------------------------------
# The whole allowlist at once
# ---------------------------------------------------------------------------
def _control_all(request: Request, session: SessionDep, user: CurrentUser, action: str):
    """Run one action across every allow-listed app container."""
    if error := _manage_error(user):
        return _redirect("/containers", error=error)
    try:
        services = [app.service for app in docker_control.list_apps()]
    except docker_control.DockerError as exc:
        return _redirect("/containers", error=str(exc))
    if not services:
        return _redirect("/containers", error="No app containers to control")

    results = docker_control.control_many(services, action)
    want_running = docker_control.expected_running(action)

    def landed(result: docker_control.ControlResult) -> bool:
        """True when the container ended in the state the action implies.

        The Docker API accepting a start/stop is not proof it worked — a start
        on a container whose process exits at once returns success and leaves it
        stopped — so the state afterwards decides what the operator is told.
        """
        if result.error or result.app is None:
            return False
        return result.app.is_running == want_running

    succeeded = [result.service for result in results if landed(result)]
    failed = [result for result in results if not landed(result)]
    audit.record(
        session, action=f"containers.{action}_all", actor=user.email, target_type="stack",
        target_id=",".join(services), ip=client_ip(request), level="warning",
        detail=f"ok={','.join(succeeded)} failed={','.join(result.service for result in failed)}",
    )
    session.commit()

    if failed:
        detail = "; ".join(
            f"{result.service}: {result.error or result.state_label}" for result in failed
        )
        return _redirect(
            "/containers",
            error=f"{len(failed)} of {len(results)} could not be "
                  f"{_PAST_TENSE.get(action, action)} — {detail[:300]}",
        )
    return _redirect(
        "/containers",
        flash=f"{len(succeeded)} app container(s) {_PAST_TENSE.get(action, action)}",
    )


@router.post("/start-all")
def start_all(request: Request, session: SessionDep, user: CurrentUser):
    """Start every app container (e.g. after bringing the stack back up)."""
    return _control_all(request, session, user, "start")


@router.post("/stop-all")
def stop_all(request: Request, session: SessionDep, user: CurrentUser):
    """Stop every app container, freeing their memory but keeping the data."""
    return _control_all(request, session, user, "stop")


@router.post("/restart-all")
def restart_all(request: Request, session: SessionDep, user: CurrentUser):
    """Restart every app container — the usual fix after a code change."""
    return _control_all(request, session, user, "restart")
