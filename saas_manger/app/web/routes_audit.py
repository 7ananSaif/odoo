"""Audit log viewer (read-only, filterable)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import or_, select

from app.deps import CurrentUser, SessionDep
from app.models.ops import AuditLog
from app.web.templating import render

router = APIRouter(prefix="/audit", tags=["audit"])

PAGE_SIZE = 100


@router.get("", response_class=HTMLResponse)
def view(request: Request, session: SessionDep, user: CurrentUser, q: str = "",
         level: str = "", page: int = 1):
    """List audit entries, newest first, with a free-text filter."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if level:
        stmt = stmt.where(AuditLog.level == level)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            AuditLog.action.ilike(like),
            AuditLog.actor.ilike(like),
            AuditLog.detail.ilike(like),
            AuditLog.target_type.ilike(like),
        ))
    page = max(1, page)
    stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE + 1)
    rows = list(session.scalars(stmt).all())
    has_next = len(rows) > PAGE_SIZE
    entries = rows[:PAGE_SIZE]
    return render(request, "audit.html", {
        "entries": entries, "q": q, "level": level, "page": page, "has_next": has_next,
    })
