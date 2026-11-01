"""The live catalogue: the shipped app list plus whatever the servers offer.

:mod:`app.services.app_catalogue` is the *shipped* list of apps the manager
sells. Real installations grow past it — a provider drops a module folder into
the addons path, an Enterprise module appears after an upgrade. Those apps must
be first-class: installable, and part of a bouquet.

This module keeps that promise without anybody editing code:

* :func:`discover` records every application a tenant's Odoo reports that the
  shipped catalogue (or an earlier discovery) does not already know;
* :func:`adopt` puts the freshly discovered apps into the white-label bouquet,
  so a new app is never left outside every bouquet.

:func:`sync` runs both and is called every time the apps screen lists a tenant,
so a newly added module folder enters the catalogue the moment an operator looks
at that tenant. Discovery is **additive**: it never removes or deactivates a
name.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogue_module import CatalogueModule
from app.models.plan import Plan, PlanModule
from app.services import app_catalogue

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def list_discovered(session: Session) -> list[CatalogueModule]:
    """The discovered apps, alphabetically."""
    stmt = select(CatalogueModule).order_by(CatalogueModule.technical_name)
    return list(session.scalars(stmt).all())


def discovered_names(session: Session) -> set[str]:
    """Technical names discovered on a server, beyond the shipped catalogue."""
    return {row.technical_name for row in list_discovered(session)}


def known_names(session: Session) -> set[str]:
    """Every app the manager knows: the shipped catalogue plus discoveries."""
    return set(app_catalogue.known_set()) | discovered_names(session)


def is_known(session: Session, name: str) -> bool:
    """True when ``name`` is in the shipped catalogue or was discovered."""
    return name in known_names(session)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
def _white_label_plan(session: Session) -> Plan | None:
    """The bouquet that authorises every app, if one is configured."""
    stmt = (
        select(Plan)
        .where(Plan.all_apps.is_(True))
        .order_by(Plan.id)
    )
    return session.scalars(stmt).first()


def discover(session: Session, apps, *, source: str = "") -> list[str]:
    """Record the applications ``apps`` reports that the catalogue lacks.

    ``apps`` is any iterable of objects carrying ``name``, ``label`` and
    ``is_app`` — the :class:`~app.services.odoo_apps.AppInfo` list the apps
    screen already reads. Only real applications are recorded: technical
    modules are dependencies Odoo pulls in by itself, not things the manager
    sells. Returns the names that were newly added.
    """
    known = known_names(session)
    added: list[str] = []
    for app in apps:
        name = (getattr(app, "name", "") or "").strip()
        if not name or name in known or not getattr(app, "is_app", False):
            continue
        session.add(CatalogueModule(
            technical_name=name,
            label=(getattr(app, "label", "") or "").strip(),
            source=source,
        ))
        known.add(name)
        added.append(name)

    if added:
        # The session runs with autoflush off, so flush here: the caller's next
        # query must already see these rows, and a bad name fails now rather
        # than at commit time.
        session.flush()
        _logger.info("catalogue: discovered %s new app(s): %s", len(added), sorted(added))
    return added


def adopt(session: Session, names: list[str]) -> Plan | None:
    """Add ``names`` to the white-label bouquet; returns that bouquet.

    A discovered app that belongs to no bouquet could only be installed for a
    single tenant by hand. Listing it in the white-label bouquet makes it part
    of the offer, which is the rule the manager enforces everywhere else.
    """
    if not names:
        return _white_label_plan(session)
    plan = _white_label_plan(session)
    if plan is None:
        _logger.warning(
            "catalogue: %s discovered but no white-label bouquet exists to adopt them",
            sorted(names),
        )
        return None

    # Append through the relationship, not ``session.add``: the collection is
    # already loaded, and going through it keeps the in-memory view in step with
    # the rows — which is what stops a second call inserting a duplicate.
    present = {module.technical_name for module in plan.modules}
    for name in names:
        if name not in present:
            plan.modules.append(PlanModule(technical_name=name))
            present.add(name)
    session.flush()
    return plan


def sync(session: Session, apps, *, source: str = "") -> list[str]:
    """Discover the apps in ``apps`` and adopt the new ones into a bouquet.

    Returns the names that were newly added; an empty list means the catalogue
    already knew everything this server offers. The caller owns the
    transaction: nothing is committed here, so a caller that is only rendering a
    page can decide whether to keep the change.
    """
    added = discover(session, apps, source=source)
    if added:
        adopt(session, added)
    return added
