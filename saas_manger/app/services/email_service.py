"""Outgoing email: invoice sending and dunning reminders.

Messages are **plain text** only, so tenant-supplied values never need markup
escaping. The SMTP configuration is read from the manager settings table (edited
on the Settings page) and falls back to `.env` values when a row is absent.

When email is disabled or unconfigured, every send becomes a no-op that is still
recorded in the audit log, so the UI stays consistent on a fresh install.
"""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy.orm import Session

from app.config import settings as env
from app.models.billing import Invoice
from app.models.tenant import Tenant
from app.security import decrypt_secret
from app.services import audit, settings_service

_logger = logging.getLogger(__name__)


class EmailError(RuntimeError):
    """Raised when a message could not be handed to the SMTP server."""


@dataclass
class Attachment:
    """A file attached to an outgoing message."""

    filename: str
    content: bytes
    mime_type: str = "application/octet-stream"


@dataclass
class EmailResult:
    """Outcome of a send attempt."""

    sent: bool
    skipped_reason: str = ""
    recipients: list[str] = field(default_factory=list)


@dataclass
class MailConfig:
    """Resolved SMTP settings for one send."""

    enabled: bool
    host: str
    port: int
    user: str
    password: str
    use_tls: bool
    use_ssl: bool
    sender: str
    sender_name: str
    timeout: int

    @property
    def is_configured(self) -> bool:
        """True when enough settings are present to attempt a send."""
        return bool(self.enabled and self.host and self.sender)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def mail_config(session: Session) -> MailConfig:
    """Resolve the SMTP configuration from settings, falling back to `.env`."""
    encrypted_password = settings_service.get_value(session, "smtp_password", "")
    password = decrypt_secret(encrypted_password) if encrypted_password else env.smtp_password
    return MailConfig(
        enabled=settings_service.get_bool(session, "email_enabled", env.email_enabled),
        host=settings_service.get_value(session, "smtp_host", env.smtp_host),
        port=settings_service.get_int(session, "smtp_port", env.smtp_port),
        user=settings_service.get_value(session, "smtp_user", env.smtp_user),
        password=password or "",
        use_tls=settings_service.get_bool(session, "smtp_use_tls", env.smtp_use_tls),
        use_ssl=settings_service.get_bool(session, "smtp_use_ssl", env.smtp_use_ssl),
        sender=settings_service.get_value(session, "email_from", env.email_from),
        sender_name=settings_service.get_value(session, "email_from_name", env.email_from_name),
        timeout=settings_service.get_int(session, "email_timeout", env.email_timeout),
    )


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
def build_message(config: MailConfig, to: list[str], subject: str, body: str,
                  attachments: list[Attachment] | None = None) -> EmailMessage:
    """Build a plain-text message with optional attachments."""
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((config.sender_name, config.sender))
    message["To"] = ", ".join(to)
    message.set_content(body)
    for attachment in attachments or []:
        maintype, _, subtype = attachment.mime_type.partition("/")
        message.add_attachment(
            attachment.content,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=attachment.filename,
        )
    return message


def send_mail(config: MailConfig, to: list[str] | str, subject: str, body: str,
              attachments: list[Attachment] | None = None) -> EmailResult:
    """Send a plain-text email. Returns a result instead of raising when disabled.

    :raises EmailError: when email is enabled but the SMTP server refused/failed.
    """
    recipients = [to] if isinstance(to, str) else [address for address in to if address]
    if not recipients:
        return EmailResult(sent=False, skipped_reason="no recipient address")
    if not config.is_configured:
        _logger.info("email disabled/unconfigured - skipping %r to %s", subject, recipients)
        return EmailResult(sent=False, skipped_reason="email not configured", recipients=recipients)

    message = build_message(config, recipients, subject, body, attachments)
    try:
        if config.use_ssl:
            client = smtplib.SMTP_SSL(config.host, config.port, timeout=config.timeout)
        else:
            client = smtplib.SMTP(config.host, config.port, timeout=config.timeout)
        with client:
            client.ehlo()
            if config.use_tls and not config.use_ssl:
                client.starttls()
                client.ehlo()
            if config.user:
                client.login(config.user, config.password)
            client.send_message(message)
    except Exception as exc:  # noqa: BLE001 - surface a single, clear error type
        _logger.error("SMTP send failed for %r: %s", subject, exc)
        raise EmailError(f"Could not send email: {exc}") from exc
    return EmailResult(sent=True, recipients=recipients)


# ---------------------------------------------------------------------------
# Invoice email
# ---------------------------------------------------------------------------
def invoice_subject(invoice: Invoice, tenant: Tenant, company_name: str) -> str:
    return f"Invoice {invoice.number} from {company_name}"


def invoice_body(invoice: Invoice, tenant: Tenant, company_name: str) -> str:
    """Plain-text covering note for an invoice."""
    lines = [
        f"Dear {tenant.contact_name or tenant.name},",
        "",
        f"Please find attached invoice {invoice.number} from {company_name}.",
        "",
        f"Invoice number : {invoice.number}",
        f"Issue date     : {invoice.issue_date:%Y-%m-%d}",
        f"Due date       : {invoice.due_date:%Y-%m-%d}",
        f"Amount due     : {invoice.balance:,.2f} {invoice.currency}",
    ]
    if invoice.period_start and invoice.period_end:
        lines.append(f"Service period : {invoice.period_start:%Y-%m-%d} to {invoice.period_end:%Y-%m-%d}")
    lines += [
        "",
        "Payment details are shown on the attached PDF.",
        "",
        "Thank you for your business.",
        company_name,
    ]
    return "\n".join(lines)


def send_invoice_email(
    session: Session,
    invoice: Invoice,
    tenant: Tenant,
    *,
    pdf_bytes: bytes,
    company: dict[str, str],
    actor: str = "system",
) -> EmailResult:
    """Email the invoice PDF to the tenant and record the attempt."""
    company_name = company.get("name") or "your provider"
    result = _send_and_audit(
        session,
        to=tenant.email,
        subject=invoice_subject(invoice, tenant, company_name),
        body=invoice_body(invoice, tenant, company_name),
        attachments=[Attachment(filename=f"{invoice.number}.pdf", content=pdf_bytes,
                                mime_type="application/pdf")],
        action="invoice.email",
        actor=actor,
        target_type="invoice",
        target_id=invoice.id,
        detail=invoice.number,
    )
    if result.sent and invoice.sent_at is None:
        invoice.sent_at = datetime.now(timezone.utc)
    return result


def send_reminder_email(
    session: Session,
    tenant: Tenant,
    subject: str,
    body: str,
    *,
    actor: str = "scheduler",
    action: str = "tenant.reminder_email",
) -> EmailResult:
    """Send a dunning/expiry reminder to a tenant's billing contact."""
    return _send_and_audit(
        session,
        to=tenant.email,
        subject=subject,
        body=body,
        attachments=[],
        action=action,
        actor=actor,
        target_type="tenant",
        target_id=tenant.id,
        detail=subject,
    )


def _send_and_audit(
    session: Session,
    *,
    to: str,
    subject: str,
    body: str,
    attachments: list[Attachment],
    action: str,
    actor: str,
    target_type: str,
    target_id: int,
    detail: str,
) -> EmailResult:
    """Send (or skip) a message and always log the outcome.

    A delivery failure is logged as an error but never raises to the caller: an
    email problem must not abort an invoice or a billing sweep.
    """
    if not to:
        audit.record(session, action=f"{action}.skipped", actor=actor, target_type=target_type,
                     target_id=target_id, level="warning", detail="no email address on file")
        return EmailResult(sent=False, skipped_reason="no email address")
    try:
        result = send_mail(mail_config(session), to, subject, body, attachments)
    except EmailError as exc:
        audit.record(session, action=f"{action}.failed", actor=actor, target_type=target_type,
                     target_id=target_id, level="error", detail=f"{detail}: {exc}")
        return EmailResult(sent=False, skipped_reason=str(exc), recipients=[to])

    if result.sent:
        audit.record(session, action=action, actor=actor, target_type=target_type,
                     target_id=target_id, detail=f"{detail} -> {to}")
    else:
        audit.record(session, action=f"{action}.skipped", actor=actor, target_type=target_type,
                     target_id=target_id, detail=f"{detail}: {result.skipped_reason}")
    return result
