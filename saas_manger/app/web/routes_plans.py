"""Plan ("bouquet") management: allowed apps, limits, pricing."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.deps import CurrentUser, SessionDep, client_ip
from app.models.plan import Plan, PlanModule
from app.services import audit, permissions, plan_service
from app.web import guards
from app.web.templating import render

router = APIRouter(prefix="/plans", tags=["plans"])


def _redirect(url: str, flash: str = "", error: str = "") -> RedirectResponse:
    from urllib.parse import urlencode  # noqa: PLC0415

    params = {}
    if flash:
        params["flash"] = flash
    if error:
        params["error"] = error
    suffix = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{url}{suffix}", status_code=303)


def _decimal(value: str | None, default: str = "0") -> Decimal:
    try:
        return Decimal((value or default).strip() or default)
    except (InvalidOperation, AttributeError):
        return Decimal(default)


def _parse_modules(raw: str) -> list[str]:
    """Split a comma/whitespace separated module list, deduplicated."""
    parts = [p.strip() for p in raw.replace("\n", ",").replace(" ", ",").split(",")]
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(part)
    return seen


@router.get("", response_class=HTMLResponse)
def list_view(request: Request, session: SessionDep, user: CurrentUser):
    plans = list(session.scalars(select(Plan).order_by(Plan.name)).all())
    return render(request, "plans/list.html", {"plans": plans})


@router.get("/new", response_class=HTMLResponse)
def new_form(request: Request, session: SessionDep, user: CurrentUser):
    return render(request, "plans/form.html", {"plan": None, "modules_raw": ""})


@router.post("/new")
def create(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    name: str = Form(...),
    code: str = Form(...),
    description: str = Form(""),
    modules: str = Form(""),
    max_users: int = Form(5),
    max_warehouses: int = Form(1),
    max_companies: int = Form(1),
    max_storage_mb: int = Form(5120),
    currency: str = Form("USD"),
    price_month: str = Form("0"),
    price_year: str = Form("0"),
    setup_fee: str = Form("0"),
    price_extra_user: str = Form("0"),
    price_extra_warehouse: str = Form("0"),
    tax_rate: str = Form("0"),
    trial_days: int = Form(14),
):
    if error := guards.permission_error(user, permissions.PERM_PLANS_MANAGE, "create plans"):
        return _redirect("/plans/new", error=error)
    code = code.strip().lower()
    if session.scalar(select(Plan).where(Plan.code == code)):
        return _redirect("/plans/new", error="A plan with this code already exists")
    plan = Plan(
        name=name.strip(), code=code, description=description,
        max_users=max_users, max_warehouses=max_warehouses, max_companies=max_companies,
        max_storage_mb=max_storage_mb, currency=currency.strip().upper() or "USD",
        price_month=_decimal(price_month), price_year=_decimal(price_year),
        setup_fee=_decimal(setup_fee), price_extra_user=_decimal(price_extra_user),
        price_extra_warehouse=_decimal(price_extra_warehouse), tax_rate=_decimal(tax_rate),
        trial_days=trial_days,
    )
    session.add(plan)
    session.flush()
    for module in _parse_modules(modules):
        session.add(PlanModule(plan_id=plan.id, technical_name=module))
    audit.record(session, action="plan.create", actor=user.email, target_type="plan",
                 target_id=plan.id, ip=client_ip(request), detail=code)
    session.commit()
    return _redirect("/plans", flash=f"Plan {plan.name} created")


@router.get("/{plan_id}/edit", response_class=HTMLResponse)
def edit_form(request: Request, session: SessionDep, user: CurrentUser, plan_id: int):
    plan = session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    return render(request, "plans/form.html", {"plan": plan, "modules_raw": ", ".join(plan.module_names)})


@router.post("/{plan_id}/edit")
def update(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    plan_id: int,
    name: str = Form(...),
    code: str = Form(...),
    description: str = Form(""),
    modules: str = Form(""),
    max_users: int = Form(5),
    max_warehouses: int = Form(1),
    max_companies: int = Form(1),
    max_storage_mb: int = Form(5120),
    currency: str = Form("USD"),
    price_month: str = Form("0"),
    price_year: str = Form("0"),
    setup_fee: str = Form("0"),
    price_extra_user: str = Form("0"),
    price_extra_warehouse: str = Form("0"),
    tax_rate: str = Form("0"),
    trial_days: int = Form(14),
    active: bool = Form(False),
):
    if error := guards.permission_error(user, permissions.PERM_PLANS_MANAGE, "edit plans"):
        return _redirect("/plans", error=error)

    plan = session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")

    plan.name = name.strip()
    plan.code = code.strip().lower()
    plan.description = description
    plan.max_users = max_users
    plan.max_warehouses = max_warehouses
    plan.max_companies = max_companies
    plan.max_storage_mb = max_storage_mb
    plan.currency = currency.strip().upper() or "USD"
    plan.price_month = _decimal(price_month)
    plan.price_year = _decimal(price_year)
    plan.setup_fee = _decimal(setup_fee)
    plan.price_extra_user = _decimal(price_extra_user)
    plan.price_extra_warehouse = _decimal(price_extra_warehouse)
    plan.tax_rate = _decimal(tax_rate)
    plan.trial_days = trial_days
    plan.active = active

    # Replace the allowed modules.
    for module in list(plan.modules):
        session.delete(module)
    session.flush()
    for module in _parse_modules(modules):
        session.add(PlanModule(plan_id=plan.id, technical_name=module))

    audit.record(session, action="plan.update", actor=user.email, target_type="plan",
                 target_id=plan.id, ip=client_ip(request), detail=plan.code)
    session.commit()
    return _redirect("/plans", flash=f"Plan {plan.name} updated")


@router.post("/{plan_id}/delete")
def delete(request: Request, session: SessionDep, user: CurrentUser, plan_id: int):
    if error := guards.permission_error(user, permissions.PERM_PLANS_MANAGE, "delete plans"):
        return _redirect("/plans", error=error)

    plan = session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    audit.record(session, action="plan.delete", actor=user.email, target_type="plan",
                 target_id=plan_id, ip=client_ip(request), level="warning", detail=plan.code)
    session.delete(plan)
    session.commit()
    return _redirect("/plans", flash="Plan deleted")


@router.get("/{plan_id}/diff", response_class=HTMLResponse)
def view_diff(request: Request, session: SessionDep, user: CurrentUser, plan_id: int):
    """Show which modules the plan adds/removes relative to base+web."""
    plan = session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    allowed = sorted(plan_service.allowed_modules(plan))
    return render(request, "plans/diff.html", {"plan": plan, "allowed": allowed})
