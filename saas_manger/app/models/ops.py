"""Operational models: versions, backups, update runs/jobs, logs, audit trail."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import PkMixin, TimestampMixin


class OdooVersion(Base, PkMixin, TimestampMixin):
    """A registered version/addon package that can be pushed to tenants."""

    __tablename__ = "odoo_versions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    odoo_series: Mapped[str] = mapped_column(String(16), nullable=False, default="19.0")
    # Modules to update for this version; empty => update 'all'.
    modules: Mapped[str] = mapped_column(Text, nullable=False, default="")  # comma separated
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    @property
    def module_list(self) -> list[str]:
        return [m.strip() for m in self.modules.split(",") if m.strip()]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OdooVersion {self.name}>"


class Backup(Base, PkMixin, TimestampMixin):
    """A database+filestore backup file produced by the manager."""

    __tablename__ = "backups"

    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=True)
    db_name: Mapped[str] = mapped_column(String(63), nullable=False, index=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="zip")
    with_filestore: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")  # manual/pre_update/pre_restore
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Backup {self.db_name} {self.path}>"


class UpdateRun(Base, PkMixin, TimestampMixin):
    """A batch update campaign (all or selected databases)."""

    __tablename__ = "update_runs"

    version_id: Mapped[int | None] = mapped_column(ForeignKey("odoo_versions.id", ondelete="SET NULL"), nullable=True)
    modules: Mapped[str] = mapped_column(Text, nullable=False, default="")  # resolved at launch
    target: Mapped[str] = mapped_column(String(16), nullable=False, default="selected")  # all/selected
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    backup_first: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")

    jobs: Mapped[list[UpdateJob]] = relationship(
        "UpdateJob", back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UpdateRun {self.id} {self.status}>"


class UpdateJob(Base, PkMixin, TimestampMixin):
    """One database within an update run."""

    __tablename__ = "update_jobs"

    run_id: Mapped[int | None] = mapped_column(ForeignKey("update_runs.id", ondelete="CASCADE"), index=True, nullable=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="SET NULL"), index=True, nullable=True)
    db_name: Mapped[str] = mapped_column(String(63), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    backup_id: Mapped[int | None] = mapped_column(ForeignKey("backups.id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rolled_back: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    run: Mapped[UpdateRun | None] = relationship("UpdateRun", back_populates="jobs")
    logs: Mapped[list[JobLog]] = relationship(
        "JobLog", back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UpdateJob {self.db_name} {self.status}>"


class JobLog(Base, PkMixin, TimestampMixin):
    """A line of output for a job."""

    __tablename__ = "job_logs"

    job_id: Mapped[int] = mapped_column(ForeignKey("update_jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")

    job: Mapped[UpdateJob] = relationship("UpdateJob", back_populates="logs")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<JobLog {self.level}: {self.message[:40]}>"


class AuditLog(Base, PkMixin, TimestampMixin):
    """Immutable trail of every management action."""

    __tablename__ = "audit_logs"

    actor: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.action} {self.target_type}:{self.target_id}>"
