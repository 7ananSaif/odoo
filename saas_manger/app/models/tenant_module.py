"""Per-tenant app decisions: manual activation and hiding.

A plan ("bouquet") is the *commercial* answer to "which apps may this tenant
run". Two situations need a decision that a plan cannot express, and both are
recorded here, one row per tenant and app:

``manual``
    The operator activated this app for **this tenant only**, even though the
    tenant's plan does not list it. It makes the app installable without
    editing the plan (which would change every other tenant on it).

``hidden``
    The app stays installed and its data keeps working, but the tenant does not
    see it: the guard hides its menus (see ``saas_tenant_guard``). "Hide" is a
    visibility switch, not a removal — uninstalling would destroy the data.

A row exists only while at least one of the two flags is set; clearing both
deletes it (see :mod:`app.services.tenant_modules`).
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import PkMixin, TimestampMixin


class TenantModule(Base, PkMixin, TimestampMixin):
    """One app decision for one tenant (manual activation and/or hiding)."""

    __tablename__ = "tenant_modules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "technical_name", name="uq_tenant_module"),
    )

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    technical_name: Mapped[str] = mapped_column(String(128), nullable=False)

    #: Activated by hand for this tenant, beyond what its plan lists.
    manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Installed but hidden from the tenant's menus.
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Free-text reason, shown on the tenant's apps screen.
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    tenant: Mapped["Tenant"] = relationship("Tenant")  # noqa: F821

    @property
    def is_empty(self) -> bool:
        """True when the row no longer carries a decision and should be dropped."""
        return not self.manual and not self.hidden

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        flags = ",".join(
            name for name, on in (("manual", self.manual), ("hidden", self.hidden)) if on
        )
        return f"<TenantModule {self.technical_name} [{flags}]>"
