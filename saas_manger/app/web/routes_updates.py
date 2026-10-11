"""Update centre: versions, batch runs, per-database jobs and logs."""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.deps import CurrentUser, SessionDep, client_ip
from app.models.enums import JobStatus
from app.models.ops import OdooVersion, UpdateJob, UpdateRun
from app.models.tenant import Tenant
from app.services import audit, tenant_service, update_service
from app.web.templating import render

router = APIRouter(prefix="/updates", tags=["updates"])


def _redirect(url: str, flash: str = "", error: str = "") -> RedirectResponse:
    from urllib.parse import urlencode  # noqa: PLC0415

    params = {}
    if flash:
        params["flash"] = flash
    if error:
        params["error"] = error
    suffix = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{url}{suffix}", status_code=303)


@router.get("", response_class=HTMLResponse)
def list_view(request: Request, session: SessionDep, user: CurrentUser):
    versions = list(session.scalars(select(OdooVersion).order_by(OdooVersion.created_at.desc())).all())
    runs = list(session.scalars(select(UpdateRun).order_by(UpdateRun.created_at.desc()).limit(25)).all())
    return render(request, "updates/list.html", {"versions": versions, "runs": runs})


@router.post("/versions")
def create_version(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    name: str = Form(...),
    odoo_series: str = Form("19.0"),
    modules: str = Form(""),
    notes: str = Form(""),
    is_current: bool = Form(False),
):
    version = OdooVersion(
        name=name.strip(), odoo_series=odoo_series.strip() or "19.0",
        modules=",".join([m.strip() for m in modules.replace("\n", ",").split(",") if m.strip()]),
        notes=notes,
    )
    session.add(version)
    session.flush()
    if is_current:
        update_service.set_current_version(session, version)
    audit.record(session, action="version.create", actor=user.email, target_type="version",
                 target_id=version.id, ip=client_ip(request), detail=version.name)
    session.commit()
    return _redirect("/updates", flash=f"Version {version.name} registered")


@router.post("/versions/{version_id}/delete")
def delete_version(request: Request, session: SessionDep, user: CurrentUser, version_id: int):
    version = session.get(OdooVersion, version_id)
    if version is None:
        raise HTTPException(404, "Version not found")
    audit.record(session, action="version.delete", actor=user.email, target_type="version",
                 target_id=version_id, ip=client_ip(request), level="warning", detail=version.name)
    session.delete(version)
    session.commit()
    return _redirect("/updates", flash="Version deleted")


@router.get("/new", response_class=HTMLResponse)
def new_run_form(request: Request, session: SessionDep, user: CurrentUser):
    versions = list(session.scalars(select(OdooVersion).order_by(OdooVersion.name)).all())
    tenants = tenant_service.list_tenants(session)
    return render(request, "updates/run_form.html", {"versions": versions, "tenants": tenants})


@router.post("/new")
def create_run(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    version_id: int = Form(0),
    modules: str = Form(""),
    target: str = Form("selected"),
    db_names: list[str] = Form(default=[]),
    backup_first: bool = Form(True),
    maintenance_mode: bool = Form(False),
    run_now: bool = Form(True),
):
    """Create an update run over the selected (or all) databases."""
    version = session.get(OdooVersion, version_id) if version_id else None
    explicit = [m.strip() for m in modules.replace("\n", ",").split(",") if m.strip()]

    if target == "all":
        targets = [t.db_name for t in tenant_service.list_tenants(session) if t.provisioned]
    else:
        targets = [db for db in db_names if db]

    if not targets:
        return _redirect("/updates/new", error="Select at least one database")

    plan = update_service.RunPlan(
        version_id=version.id if version else None,
        modules=update_service.resolve_modules(session, version, explicit),
        db_names=targets,
        backup_first=backup_first,
        maintenance_mode=maintenance_mode,
        target=target,
    )
    run = update_service.create_run(session, plan, created_by=user.email)
    audit.record(session, action="update.run_created", actor=user.email, target_type="update_run",
                 target_id=run.id, ip=client_ip(request),
                 detail=f"{len(targets)} dbs modules={plan.modules}")
    session.commit()

    if run_now:
        from app.workers.tasks import run_update_run  # noqa: PLC0415

        run_update_run.delay(run.id)

    return _redirect(f"/updates/runs/{run.id}", flash="Update run created")


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, session: SessionDep, user: CurrentUser, run_id: int):
    run = session.get(UpdateRun, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return render(request, "updates/run_detail.html", {"run": run})


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, session: SessionDep, user: CurrentUser, job_id: int):
    job = session.get(UpdateJob, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return render(request, "updates/job_detail.html", {"job": job, "run": job.run})


@router.post("/jobs/{job_id}/retry")
def retry_job(request: Request, session: SessionDep, user: CurrentUser, job_id: int):
    job = session.get(UpdateJob, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    job.status = JobStatus.PENDING.value
    job.attempt = (job.attempt or 1) + 1
    audit.record(session, action="update.job_retry", actor=user.email, target_type="update_job",
                 target_id=job.id, ip=client_ip(request), detail=job.db_name)
    session.commit()
    from app.workers.tasks import run_update_job  # noqa: PLC0415

    run_update_job.delay(job.id)
    return _redirect(f"/updates/jobs/{job.id}", flash="Retry queued")


@router.get("/runs/{run_id}/logs.txt")
def run_logs(request: Request, session: SessionDep, user: CurrentUser, run_id: int):
    """Download every log line of a run as a text file."""
    run = session.get(UpdateRun, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    lines: list[str] = []
    for job in run.jobs:
        lines.append(f"===== {job.db_name} [{job.status}] =====")
        for entry in job.logs:
            lines.append(f"{entry.created_at:%Y-%m-%d %H:%M:%S} [{entry.level}] {entry.message}")
        lines.append("")
    from fastapi.responses import PlainTextResponse  # noqa: PLC0415

    return PlainTextResponse(
        "\n".join(lines),
        headers={"Content-Disposition": f"attachment; filename=run_{run_id}.log"},
    )
