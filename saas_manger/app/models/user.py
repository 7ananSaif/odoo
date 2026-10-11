"""The manager operator account (single owner, with optional 2FA)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import PkMixin, TimestampMixin


class User(Base, PkMixin, TimestampMixin):
    """An owner account able to log into the manager."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Role decides what the account may do (see app.services.permissions):
    # owner > admin > operator > viewer. `is_superuser` is kept in sync with the
    # role (owner/admin are superusers) for backwards compatibility.
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="owner", index=True)

    # 2FA (TOTP). The secret is stored encrypted (Fernet).
    totp_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_logins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def apply_role(self, role: str) -> None:
        """Set ``role`` and keep the legacy ``is_superuser`` flag in sync.

        ``is_superuser`` predates roles and is still consulted as a fallback for
        rows created before the ``role`` column existed; owners and admins stay
        superusers so nothing that checks the old flag breaks.
        """
        from app.services.permissions import ROLE_ADMIN, ROLE_OWNER, normalize_role  # noqa: PLC0415

        self.role = normalize_role(role)
        self.is_superuser = self.role in (ROLE_OWNER, ROLE_ADMIN)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User {self.id} {self.email}>"
