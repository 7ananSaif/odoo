"""Pytest fixtures: an isolated SQLite database and a configured app."""
from __future__ import annotations

import os

# --- Environment MUST be set before any `app.*` import ---------------------
from cryptography.fernet import Fernet

os.environ.setdefault("SECRETS_KEY", Fernet.generate_key().decode())
os.environ.setdefault("SECRET_KEY", "test-session-secret")
os.environ.setdefault("MANAGER_DB_URL", "sqlite://")
os.environ.setdefault("ODOO_MANAGER_TOKEN", "test-manager-token")
os.environ.setdefault("ODOO_BASE_URL", "http://localhost:8069")
os.environ.setdefault("ODOO_DOMAIN", "localhost")
os.environ.setdefault("SCHEDULER_ENABLED", "false")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.db as db  # noqa: E402
from app.services import settings_service  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    """Point the app at a single shared in-memory SQLite database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db.engine = engine
    db.SessionLocal.configure(bind=engine)
    db.create_all()
    with db.SessionLocal() as session:
        settings_service.seed_defaults(session)
        session.commit()


@pytest.fixture()
def session():
    """A fresh session per test, rolled back afterwards."""
    with db.SessionLocal() as session:
        yield session
        session.rollback()


@pytest.fixture()
def client():
    """A FastAPI TestClient (for route smoke tests)."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from app.main import app  # noqa: PLC0415

    return TestClient(app)
