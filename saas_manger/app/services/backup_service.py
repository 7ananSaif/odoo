"""Backup and restore a tenant database, tracked in the ``backups`` table."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.ops import Backup
from app.models.tenant import Tenant
from app.services import pg_tools

_logger = logging.getLogger(__name__)


class BackupError(RuntimeError):
    """Raised when a backup or restore operation fails."""


def create_backup(session: Session, tenant: Tenant, *, reason: str = "manual",
                  with_filestore: bool = True, fmt: str = "zip") -> Backup:
    """Dump a tenant database (+ filestore) and record the artefact."""
    record = Backup(
        tenant_id=tenant.id,
        db_name=tenant.db_name,
        path="",
        format=fmt,
        with_filestore=with_filestore,
        reason=reason,
        succeeded=False,
    )
    session.add(record)
    session.flush()
    try:
        artefact = pg_tools.dump_database(tenant.db_name, fmt=fmt, with_filestore=with_filestore)
        record.path = str(artefact)
        record.size_bytes = artefact.stat().st_size if artefact.exists() else 0
        record.succeeded = True
        tenant.last_backup_at = datetime.now(timezone.utc)
    except Exception as exc:  # noqa: BLE001 - recorded then re-raised
        record.message = str(exc)
        record.succeeded = False
        raise BackupError(f"backup failed for {tenant.db_name}: {exc}") from exc
    finally:
        session.flush()
    return record


def restore_backup(session: Session, tenant: Tenant, backup: Backup) -> None:
    """Restore a tenant from a previously recorded backup.

    WARNING: the current database is dropped and recreated from the backup.
    """
    if not backup.succeeded or not backup.path:
        raise BackupError("Cannot restore: the backup was not successful")
    # Drop and recreate the (empty) database, then restore the dump into it.
    pg_tools.terminate_connections(tenant.db_name)
    pg_tools.drop_database(tenant.db_name, terminate_connections=False)
    pg_tools.create_database(tenant.db_name)
    try:
        pg_tools.restore_database(tenant.db_name, backup.path)
    except Exception as exc:  # noqa: BLE001
        raise BackupError(f"restore failed for {tenant.db_name}: {exc}") from exc


def last_backup(session: Session, tenant_id: int) -> Backup | None:
    from sqlalchemy import select  # noqa: PLC0415

    return session.scalar(
        select(Backup)
        .where(Backup.tenant_id == tenant_id, Backup.succeeded.is_(True))
        .order_by(Backup.created_at.desc())
    )


def list_backups(session: Session, tenant_id: int | None = None) -> list[Backup]:
    from sqlalchemy import select  # noqa: PLC0415

    stmt = select(Backup).order_by(Backup.created_at.desc())
    if tenant_id is not None:
        stmt = stmt.where(Backup.tenant_id == tenant_id)
    return list(session.scalars(stmt).all())
