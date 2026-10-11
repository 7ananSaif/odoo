"""Cookie-domain rules for the "Open in Odoo" auto-login hand-off.

A browser cannot be signed into an Odoo that lives on a different origin just by
following a link, so the manager authenticates server-side, obtains the Odoo
``session_id`` and hands it to the browser as a cookie.  Odoo validates only the
cookie value, and cookies are scoped to a **host** (not a port), so this works
whenever the manager can set a cookie the Odoo host will accept:

* same host, different port (local dev: 127.0.0.1:8090 → 127.0.0.1:8069) —
  a host-only cookie is enough;
* shared registrable domain (manager.example.com → acme.example.com) — the
  cookie is set with ``Domain=.example.com``.

Anything else (manager.example.com → tenant.otherdomain.com) cannot be handed a
cookie; the caller detects ``None`` and falls back to the plain login page.

The registrable-domain rule here is the common two-label heuristic and does not
know public-suffix list oddities such as ``co.uk``; deployments on such a suffix
should set ``ODOO_PUBLIC_URL`` to the same host as the manager, or accept the
manual login fallback.
"""
from __future__ import annotations

SESSION_COOKIE = "session_id"


def host_of(value: str | None) -> str:
    """Extract the lower-cased host from a URL, ``host:port`` pair or host."""
    if not value:
        return ""
    host = str(value).strip().lower()
    if "//" in host:
        host = host.split("//", 1)[1]
    host = host.split("/", 1)[0]
    if "@" in host:
        host = host.rsplit("@", 1)[1]
    if host.startswith("["):  # IPv6 literal, e.g. [::1]:8069
        return host[1:].split("]", 1)[0]
    return host.split(":", 1)[0]


def _is_ipv4(host: str) -> bool:
    parts = host.split(".")
    return len(parts) == 4 and all(part.isdigit() for part in parts)


def registrable_domain(host: str) -> str:
    """Return the registrable domain of ``host`` (``a.b.example.com`` → ``example.com``)."""
    if not host:
        return ""
    labels = host.split(".")
    if len(labels) <= 2 or _is_ipv4(host) or all(part.isdigit() for part in labels):
        return host
    return ".".join(labels[-2:])


def cookie_domain_for(manager_host: str, odoo_host: str) -> str | None:
    """Return the ``Domain=`` value a session cookie needs, or None if impossible.

    * ``""``   → set a host-only cookie (manager and Odoo share the host);
    * ``".x"`` → set the cookie for the shared registrable domain;
    * ``None`` → the two hosts cannot share a cookie; caller must fall back.
    """
    manager = host_of(manager_host)
    odoo = host_of(odoo_host)
    if not manager or not odoo:
        return None
    if manager == odoo:
        return ""
    parent = registrable_domain(odoo)
    if not parent:
        return None
    manager_covered = manager == parent or manager.endswith("." + parent)
    odoo_covered = odoo == parent or odoo.endswith("." + parent)
    if manager_covered and odoo_covered:
        return "." + parent
    return None


def same_site_managed(manager_host: str, odoo_host: str) -> bool:
    """True when a session cookie can be handed from manager to Odoo."""
    return cookie_domain_for(manager_host, odoo_host) is not None
