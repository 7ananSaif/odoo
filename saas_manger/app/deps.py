"""FastAPI dependencies: database session and authenticated owner."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models.user import User
from app.security import load_session_token

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(request: Request, session: SessionDep) -> User | None:
    """Return the logged-in owner, or None when there is no valid session."""
    token = request.cookies.get(settings.session_cookie)
    if not token:
        return None
    data = load_session_token(token)
    if data is None:
        return None
    user = session.get(User, data.user_id)
    if user is None or not user.is_active:
        return None
    return user


def require_user(request: Request, session: SessionDep) -> User:
    """Dependency that enforces an authenticated owner, redirecting to /login."""
    user = get_current_user(request, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return user


CurrentUser = Annotated[User, Depends(require_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user)]


def client_ip(request: Request) -> str:
    """Best-effort client IP, honouring a proxy's X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""
