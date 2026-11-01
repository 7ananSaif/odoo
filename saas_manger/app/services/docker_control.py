"""Start, stop and restart the stack's application containers.

The manager runs *inside* a container, so it cannot shell out to
``docker compose``. It speaks the Docker Engine API directly over the socket the
compose file bind-mounts at ``DOCKER_SOCKET`` (``/var/run/docker.sock`` by
default), using httpx's Unix-domain transport.

Only the compose *services* named by ``APP_SERVICES`` may be touched, and only
when they belong to the ``COMPOSE_PROJECT`` compose project. Two further rails
apply on top of the allowlist:

* :data:`PROTECTED_SERVICES` — the database, the broker/cache, certbot and the
  manager's own three services — are refused even if somebody adds them to
  ``APP_SERVICES``; stopping any of them takes the panel (or the whole stack)
  down with it.
* only the fixed :data:`ACTIONS` verbs are accepted, so no arbitrary Docker API
  path can be reached through the UI.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

from app.config import settings

_logger = logging.getLogger(__name__)

# Never controllable, whatever APP_SERVICES says. Stopping the database, the
# broker/cache or the manager itself takes down the panel that is doing the
# stopping, and certbot must keep running for certificate renewal.
PROTECTED_SERVICES = frozenset({
    "db",
    "redis",
    "rabbitmq",
    "certbot",
    "saas-manager-web",
    "saas-manager-worker",
    "saas-manager-beat",
})

#: The only verbs the panel will forward to the daemon.
ACTIONS = ("start", "stop", "restart")

#: Docker's container state → the wording used in the UI.
STATE_LABELS = {
    "running": "running",
    "exited": "stopped",
    "created": "created",
    "paused": "paused",
    "restarting": "restarting",
    "removing": "removing",
    "dead": "dead",
}

_SERVICE_LABEL = "com.docker.compose.service"
_PROJECT_LABEL = "com.docker.compose.project"


class DockerError(RuntimeError):
    """The daemon could not be reached, or it refused the request."""


@dataclass(frozen=True)
class AppContainer:
    """One controllable app container, as shown on the Apps page."""

    service: str
    container_id: str
    name: str
    state: str
    status: str
    image: str
    health: str = ""
    created: int = 0

    @property
    def is_running(self) -> bool:
        """True when the container is actually up."""
        return self.state == "running"

    @property
    def state_label(self) -> str:
        """Human wording for the container state."""
        return STATE_LABELS.get(self.state, self.state)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
def socket_available() -> bool:
    """True when the Docker socket is mounted into this container."""
    return bool(settings.docker_socket) and os.path.exists(settings.docker_socket)


def _client(timeout: float) -> httpx.Client:
    if not socket_available():
        raise DockerError(
            f"The Docker socket is not available at {settings.docker_socket!r}. "
            "Mount /var/run/docker.sock into the saas-manager-web service to enable "
            "the Apps panel."
        )
    transport = httpx.HTTPTransport(uds=settings.docker_socket)
    return httpx.Client(transport=transport, base_url="http://docker", timeout=timeout)


def _request(method: str, path: str, *, timeout: float = 30.0) -> httpx.Response:
    """Call the Docker API, translating transport and API errors."""
    if not socket_available():
        raise DockerError(
            f"The Docker socket is not available at {settings.docker_socket!r}. "
            "Mount /var/run/docker.sock into the saas-manager-web service to enable "
            "the Apps panel."
        )
    try:
        with _client(timeout) as client:
            response = client.request(method, path)
    except httpx.HTTPError as exc:
        raise DockerError(f"Cannot reach the Docker daemon: {exc}") from exc
    except OSError as exc:  # socket missing, permission denied, daemon down
        raise DockerError(f"Cannot open the Docker socket: {exc}") from exc
    if response.status_code >= 400:
        raise DockerError(_error_message(response))
    return response


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
        message = payload.get("message") if isinstance(payload, dict) else None
    except ValueError:
        message = response.text[:200]
    return f"Docker API {response.status_code}: {message or 'unknown error'}"


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------
def allowlist() -> tuple[str, ...]:
    """App services the panel may control, in configuration order.

    ``PROTECTED_SERVICES`` are stripped here rather than merely left out of the
    shipped default, so a careless edit to ``APP_SERVICES`` cannot expose them.
    """
    configured = [
        service.strip()
        for service in (settings.app_services or "").split(",")
    ]
    seen: list[str] = []
    for service in configured:
        if service and service not in PROTECTED_SERVICES and service not in seen:
            seen.append(service)
    return tuple(seen)


def _matches_project(labels: dict) -> bool:
    """True when the container belongs to the configured compose project."""
    if not settings.compose_project:
        return True
    return labels.get(_PROJECT_LABEL, "") == settings.compose_project


def _health_from_status(status: str) -> str:
    if "unhealthy" in status:
        return "unhealthy"
    if "healthy" in status:
        return "healthy"
    if "starting" in status:
        return "starting"
    return ""


def _to_app(item: dict, service: str) -> AppContainer:
    names = item.get("Names") or []
    status = item.get("Status", "")
    return AppContainer(
        service=service,
        container_id=str(item.get("Id", "")),
        name=(names[0].lstrip("/") if names else service),
        state=item.get("State", "unknown"),
        status=status,
        image=item.get("Image", ""),
        health=_health_from_status(status),
        created=int(item.get("Created", 0) or 0),
    )


def _is_canonical_name(service: str, name: str) -> bool:
    """True when ``name`` looks like this project's own container for ``service``.

    `docker compose` names containers ``<project>-<service>-<n>``. Orphans left
    by earlier runs keep the compose *labels* without following that pattern, so
    a service can appear several times and the name is the tie-breaker.
    """
    prefix = f"{settings.compose_project}-{service}-" if settings.compose_project else ""
    if not prefix or not name.startswith(prefix):
        return False
    return name[len(prefix):].isdigit()


def _select(candidates: list[AppContainer]) -> AppContainer:
    """The single container to act on when several claim the same service.

    Prefer, in order: one that is actually running, one named the canonical
    compose way, and the most recently created. Acting on an old orphan would
    leave the real container untouched while reporting success.
    """
    return max(
        candidates,
        key=lambda app: (
            app.is_running,
            _is_canonical_name(app.service, app.name),
            app.created,
        ),
    )


def _containers() -> list[dict]:
    """Every container the daemon knows about, running or not."""
    return list(_request("GET", "/containers/json?all=true").json())


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def list_apps() -> list[AppContainer]:
    """The allow-listed app containers, ordered as configured.

    Services with no container (never created, or removed) are omitted; a
    service with several containers (old orphans) is reduced to one by
    :func:`_select`.
    """
    services = allowlist()
    if not services:
        return []
    candidates: dict[str, list[AppContainer]] = {}
    for item in _containers():
        labels = item.get("Labels") or {}
        service = labels.get(_SERVICE_LABEL, "")
        if service in services and _matches_project(labels):
            candidates.setdefault(service, []).append(_to_app(item, service))
    return [_select(candidates[service]) for service in services if candidates.get(service)]


def find_container_id(service: str) -> str:
    """Return the container id to act on for ``service``, checking the allowlist."""
    if service not in allowlist():
        raise DockerError(f"{service!r} is not a controllable app service")
    app = describe(service)
    if app is None or not app.container_id:
        raise DockerError(f"No container found for {service!r}")
    return app.container_id


def describe(service: str) -> AppContainer | None:
    """The current state of one app container, or None when it has no container."""
    for app in list_apps():
        if app.service == service:
            return app
    return None


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------
def control(service: str, action: str) -> AppContainer | None:
    """Run ``start``/``stop``/``restart`` on one app service.

    Returns the container's state afterwards (None if the daemon reports no
    container for the service, which happens while it is being recreated).
    """
    if action not in ACTIONS:
        raise DockerError(f"Unsupported action {action!r}")
    container_id = find_container_id(service)
    _logger.info("apps: %s %s (%s)", action, service, container_id[:12])
    _request("POST", f"/containers/{container_id}/{action}", timeout=120.0)
    return describe(service)


def expected_running(action: str) -> bool:
    """Whether ``action`` should leave a container running."""
    return action != "stop"


@dataclass(frozen=True)
class ControlResult:
    """What happened to one service, and the state it ended in."""

    service: str
    app: AppContainer | None = None
    error: str = ""

    @property
    def state_label(self) -> str:
        """The container's state, or a note that there is none."""
        return self.app.state_label if self.app else "no container"


def control_many(services, action: str) -> list[ControlResult]:
    """Run an action across several services, reporting every outcome.

    Unlike :func:`control` it never raises: a failing service yields a
    :class:`ControlResult` carrying the error, so the caller can act on the ones
    that worked and still explain the ones that did not.
    """
    results: list[ControlResult] = []
    for service in services:
        try:
            results.append(ControlResult(service=service, app=control(service, action)))
        except DockerError as exc:
            results.append(ControlResult(service=service, error=str(exc)))
    return results
