"""Apps discovered on a tenant's Odoo server that the built-in catalogue lacks.

The built-in catalogue in :mod:`app.services.app_catalogue` is the *shipped*
list of apps the manager sells. Real installations grow beyond it: a provider
drops a module folder into the addons path, or an Enterprise module appears
after an upgrade. Those apps must not be second-class — an app the server
offers has to be installable and has to belong to a bouquet.

This table is where such apps are remembered, one row per technical name. The
manager fills it automatically whenever it lists a tenant's apps, and the first
discovered app is also added to the white-label bouquet (see
:mod:`app.services.catalogue_service`). Discovery is additive only: nothing here
is ever deleted by the app itself.
"""
from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PkMixin, TimestampMixin


class CatalogueModule(Base, PkMixin, TimestampMixin):
    """A module found on a server that the built-in catalogue did not know."""

    __tablename__ = "catalogue_modules"

    #: Odoo technical name, the identity of the module.
    technical_name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    #: Human label last seen for it (informational only).
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    #: Where it came from, e.g. the tenant database it was first seen on.
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    #: Kept for symmetry with other listings; discovery never deactivates a row.
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<CatalogueModule {self.technical_name}>"
