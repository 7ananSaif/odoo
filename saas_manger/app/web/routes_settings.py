"""Settings: company, invoicing, email (SMTP) and automation defaults."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.deps import CurrentUser, SessionDep, client_ip
from app.models.settings import Setting
from app.security import encrypt_secret
from app.services import audit, settings_service
from app.web.templating import render

router = APIRouter(prefix="/settings", tags=["settings"])

# Every editable, non-secret key exposed on the page, with label and group.
FIELDS: list[dict[str, str]] = [
    # --- Company ---------------------------------------------------------
    {"key": "company_name", "label": "Company name", "group": "company"},
    {"key": "company_email", "label": "Billing email", "group": "company"},
    {"key": "company_phone", "label": "Billing phone", "group": "company"},
    {"key": "company_tax_id", "label": "Tax / VAT number", "group": "company"},
    {"key": "company_logo", "label": "Logo file path", "group": "company"},
    {"key": "company_address", "label": "Company address", "group": "company", "type": "textarea"},
    {"key": "bank_details", "label": "Bank details (shown on invoices)", "group": "company",
     "type": "textarea"},
    # --- Invoicing -------------------------------------------------------
    {"key": "default_currency", "label": "Default currency", "group": "invoicing"},
    {"key": "default_tax_rate", "label": "Default tax rate (0.19 = 19%)", "group": "invoicing"},
    {"key": "invoice_prefix", "label": "Invoice prefix", "group": "invoicing"},
    {"key": "invoice_next_number", "label": "Next invoice number", "group": "invoicing",
     "type": "number"},
    {"key": "grace_days", "label": "Grace days before suspension", "group": "invoicing",
     "type": "number"},
    {"key": "trial_days", "label": "Default trial days", "group": "invoicing", "type": "number"},
    {"key": "late_fee_percent", "label": "Late fee percent", "group": "invoicing"},
    {"key": "payment_methods", "label": "Payment methods (comma separated)", "group": "invoicing"},
    # --- Email (SMTP) ----------------------------------------------------
    {"key": "email_enabled", "label": "Enable sending email", "group": "email", "type": "bool"},
    {"key": "smtp_host", "label": "SMTP host", "group": "email"},
    {"key": "smtp_port", "label": "SMTP port", "group": "email", "type": "number"},
    {"key": "smtp_user", "label": "SMTP username", "group": "email"},
    {"key": "smtp_password", "label": "SMTP password", "group": "email", "type": "password"},
    {"key": "smtp_use_tls", "label": "Use STARTTLS (port 587)", "group": "email", "type": "bool"},
    {"key": "smtp_use_ssl", "label": "Use implicit TLS/SSL (port 465)", "group": "email",
     "type": "bool"},
    {"key": "email_from", "label": "From address", "group": "email"},
    {"key": "email_from_name", "label": "From name", "group": "email"},
    # --- Automation ------------------------------------------------------
    {"key": "dunning_enabled", "label": "Enable dunning reminders", "group": "automation",
     "type": "bool"},
    {"key": "reminder_days_before", "label": "Reminder: days before expiry", "group": "automation",
     "type": "number"},
    {"key": "reminder_days_after", "label": "Reminder: days after due date", "group": "automation",
     "type": "number"},
    {"key": "auto_suspend", "label": "Auto-suspend after grace", "group": "automation",
     "type": "bool"},
    {"key": "auto_reactivate", "label": "Auto-reactivate when paid", "group": "automation",
     "type": "bool"},
]

EDITABLE_KEYS: list[str] = [field["key"] for field in FIELDS]
PASSWORD_KEYS = {field["key"] for field in FIELDS if field.get("type") == "password"}
GROUP_TITLES = {
    "company": "Company & invoicing",
    "invoicing": "Billing defaults",
    "email": "Email (SMTP)",
    "automation": "Automation",
}


def _bool_value(raw: str) -> bool:
    return raw.strip().lower() in ("1", "true", "yes", "on")


@router.get("", response_class=HTMLResponse)
def view(request: Request, session: SessionDep, user: CurrentUser):
    settings_service.seed_defaults(session)
    session.commit()
    rows = {
        row.key: row
        for row in session.scalars(select(Setting).where(Setting.key.in_(EDITABLE_KEYS))).all()
    }
    groups: dict[str, list[dict]] = {}
    for field in FIELDS:
        key = field["key"]
        raw = rows[key].value if key in rows else ""
        # Never echo a stored password: the field starts blank and "leave empty to keep".
        if key in PASSWORD_KEYS and raw:
            raw = ""
        groups.setdefault(field["group"], []).append({
            "key": key,
            "label": field["label"],
            "value": raw,
            "type": field.get("type", "text"),
            "checked": _bool_value(raw) if field.get("type") == "bool" else False,
        })
    sections = [
        {"title": GROUP_TITLES.get(group, group.title()), "fields": fields}
        for group, fields in groups.items()
    ]
    password_set = bool(rows.get("smtp_password") and rows["smtp_password"].value)
    return render(request, "settings.html", {"sections": sections, "password_set": password_set})


@router.post("")
async def save(request: Request, session: SessionDep, user: CurrentUser):
    """Persist every submitted setting, encrypting the SMTP password at rest."""
    form = await request.form()
    for field in FIELDS:
        key = field["key"]
        field_type = field.get("type", "text")
        if field_type == "bool":
            value = "true" if form.get(key) else "false"
        elif key in PASSWORD_KEYS:
            submitted = str(form.get(key, "")).strip()
            if not submitted:
                continue  # keep the stored password when the field is left blank
            value = encrypt_secret(submitted) or ""
        else:
            value = str(form.get(key, "")).strip()
        settings_service.set_value(session, key, value)
    audit.record(session, action="settings.save", actor=user.email, ip=client_ip(request),
                 detail=f"{len(FIELDS)} keys")
    session.commit()
    return RedirectResponse("/settings?flash=Settings+saved", status_code=303)
