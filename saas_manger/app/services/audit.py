"""Write-only audit trail. Every management action funnels through here."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.ops import AuditLog


def record(
    session: Session,
    *,
    action: str,
    actor: str = "",
    target_type: str = "",
    target_id: str | int = "",
    level: str = "info",
    ip: str = "",
    detail: str = "",
) -> AuditLog:
    """Append an immutable audit entry and flush it so it survives a later rollback-of-work."""
    entry = AuditLog(
        action=action,
        actor=actor or "system",
        target_type=target_type,
        target_id=str(target_id),
        level=level,
        ip=ip,
        detail=detail,
    )
    session.add(entry)
    session.flush()
    return entry
