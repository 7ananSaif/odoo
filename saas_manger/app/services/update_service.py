"""Batch updates: backup first, bounded parallelism, per-DB status/logs, rollback."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import JobStatus
from app.models.ops import JobLog, OdooVersion, UpdateJob, UpdateRun
from app.models.tenant import Tenant
from app.services import backup_service, odoo_cli, tenant_service

_logger = logging.getLogger(__name__)


class UpdateError(RuntimeError):
    """Raised for invalid update requests."""


@dataclass
class RunPlan:
    """A resolved update request before it becomes database rows."""

    version_id: int | None
    modules: list[str]
    db_names: list[str]
    backup_first: bool = True
    maintenance_mode: bool = False
    target: str = "selected"


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
def log(session: Session, job: UpdateJob, message: str, level: str = "info") -> None:
    """Append a timestamped log line to a job."""
    session.add(JobLog(job_id=job.id, level=level, message=message))
    session.flush()
    _logger.log(logging.ERROR if level == "error" else logging.INFO, "[%s] %s", job.db_name, message)


# ---------------------------------------------------------------------------
# run creation
# ---------------------------------------------------------------------------
def resolve_modules(session: Session, version: OdooVersion | None, explicit: list[str] | None) -> list[str]:
    """Return the module list to update ("all" is represented as ['all'])."""
    if explicit:
        return explicit
    if version and version.module_list:
        return version.module_list
    return ["all"]


def create_run(session: Session, plan: RunPlan, *, created_by: str = "") -> UpdateRun:
    """Create an UpdateRun with one job per target database."""
    if not plan.db_names:
        raise UpdateError("No target database selected")
    run = UpdateRun(
        version_id=plan.version_id,
        modules=",".join(plan.modules),
        target=plan.target,
        status=JobStatus.PENDING.value,
        backup_first=plan.backup_first,
        maintenance_mode=plan.maintenance_mode,
        created_by=created_by,
    )
    session.add(run)
    session.flush()

    for db_name in plan.db_names:
        tenant = session.scalar(select(Tenant).where(Tenant.db_name == db_name))
        session.add(UpdateJob(
            run_id=run.id,
            tenant_id=tenant.id if tenant else None,
            db_name=db_name,
            status=JobStatus.PENDING.value,
        ))
    session.flush()
    return run


def set_current_version(session: Session, version: OdooVersion) -> None:
    """Mark ``version`` as the current one and unmark the others."""
    for other in session.scalars(select(OdooVersion)).all():
        other.is_current = other.id == version.id
    session.flush()


# ---------------------------------------------------------------------------
# job processing (called by the worker, one DB at a time)
# ---------------------------------------------------------------------------
def process_job(session: Session, job_id: int) -> str:
    """Run a single update job. Returns the final status string.

    Steps: mark running → (optional) suspend/maintenance → backup → run the
    Odoo CLI update → mark success, or on failure roll back from the backup.
    """
    job = session.get(UpdateJob, job_id)
    if job is None:
        raise UpdateError(f"Unknown job {job_id}")
    run = session.get(UpdateRun, job.run_id) if job.run_id else None

    tenant = session.get(Tenant, job.tenant_id) if job.tenant_id else None
    modules = [m for m in (run.modules.split(",") if run and run.modules else []) if m] or ["all"]

    job.status = JobStatus.RUNNING.value
    job.started_at = _now()
    session.flush()
    log(session, job, f"start: update modules {modules}")

    # 1. maintenance mode (best-effort: tenant shows read-only while updating)
    if run and run.maintenance_mode and tenant:
        try:
            tenant_service.push_status_suspended(tenant)
            log(session, job, "maintenance mode enabled")
        except Exception as exc:  # noqa: BLE001
            log(session, job, f"maintenance mode could not be enabled: {exc}", "warning")

    # 2. backup first
    backup = None
    if run and run.backup_first and tenant:
        try:
            backup = backup_service.create_backup(session, tenant, reason="pre_update")
            job.backup_id = backup.id
            log(session, job, f"backup created: {backup.path}")
        except Exception as exc:  # noqa: BLE001
            job.status = JobStatus.FAILED.value
            job.finished_at = _now()
            log(session, job, f"backup failed, aborting: {exc}", "error")
            session.flush()
            return job.status

    # 3. run the update via the CLI (owner-authorised path)
    try:
        result = odoo_cli.run(job.db_name, update_modules=modules)
        tail = "\n".join(result.output.strip().splitlines()[-20:])
        for line in tail.splitlines():
            log(session, job, line)
        if not result.ok:
            raise UpdateError(f"odoo-bin exited with code {result.returncode}")
        job.status = JobStatus.SUCCESS.value
        if tenant:
            tenant.last_update_at = _now()
        log(session, job, "success")
    except Exception as exc:  # noqa: BLE001
        log(session, job, f"update failed: {exc}", "error")
        # 4. rollback from the backup we made
        if backup is not None and tenant is not None:
            try:
                backup_service.restore_backup(session, tenant, backup)
                job.rolled_back = True
                log(session, job, "rolled back from backup")
            except Exception as rexc:  # noqa: BLE001
                log(session, job, f"rollback failed: {rexc}", "error")
        job.status = JobStatus.FAILED.value
    finally:
        # 5. leave maintenance mode
        if run and run.maintenance_mode and tenant:
            try:
                tenant_service.push_status_active(tenant)
            except Exception:  # noqa: BLE001
                pass
        job.finished_at = _now()
        session.flush()

    return job.status


def finalize_run(session: Session, run_id: int) -> str:
    """Compute and store the overall status of a run."""
    run = session.get(UpdateRun, run_id)
    if run is None:
        raise UpdateError(f"Unknown run {run_id}")
    statuses = {job.status for job in run.jobs}
    if statuses <= {JobStatus.SUCCESS.value}:
        run.status = JobStatus.SUCCESS.value
    elif statuses & {JobStatus.RUNNING.value, JobStatus.PENDING.value}:
        run.status = JobStatus.RUNNING.value
    elif JobStatus.SUCCESS.value in statuses:
        run.status = "partial"
    else:
        run.status = JobStatus.FAILED.value
    if run.status not in (JobStatus.RUNNING.value,):
        run.finished_at = _now()
    session.flush()
    return run.status


def pending_job_ids(session: Session, run_id: int) -> list[int]:
    return [
        job.id for job in session.scalars(
            select(UpdateJob).where(UpdateJob.run_id == run_id, UpdateJob.status == JobStatus.PENDING.value)
        ).all()
    ]


def _now() -> datetime:
    return datetime.now(timezone.utc)
