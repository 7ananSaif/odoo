"""Database engine, session factory and declarative base."""
from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.manager_db_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for every manager model."""


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a transactional session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for worker/CLI code: commit on success, rollback on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Lightweight migrations
# ---------------------------------------------------------------------------
# ``Base.metadata.create_all`` only creates *missing* tables — it never alters
# an existing one.  Columns added to a model after a database already exists
# therefore need an explicit, idempotent DDL step.  Every such step lives here
# so both ``scripts/init_db.py`` and the container entrypoint pick it up.
def _migrate(conn) -> None:
    """Apply the DDL that ``create_all`` cannot express, idempotently."""
    from sqlalchemy import inspect, text  # noqa: PLC0415

    inspector = inspect(conn)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "role" not in columns:
        # Added with role-based permissions.  Existing rows inherit their
        # legacy ``is_superuser`` flag: superusers become owners, everyone
        # else the least-privileged role.  (The column default is applied
        # first, then corrected, so the ADD COLUMN itself stays trivial.)
        conn.execute(text(
            "ALTER TABLE users ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'owner'"
        ))
        conn.execute(text(
            "UPDATE users SET role = CASE WHEN is_superuser THEN 'owner' ELSE 'viewer' END"
        ))

    indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_role" not in indexes:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)"))


def run_migrations() -> None:
    """Apply every idempotent migration in its own transaction."""
    with engine.begin() as conn:
        _migrate(conn)


def create_all() -> None:
    """Create every table, then apply lightweight migrations.

    Used by ``scripts/init_db.py`` and the container entrypoint.  Safe to run
    on every boot: ``create_all`` skips existing tables and ``run_migrations``
    is a no-op once the schema is current.
    """
    # Import models so they register on Base.metadata before create_all().
    import app.models  # noqa: F401, PLC0415

    Base.metadata.create_all(bind=engine)
    run_migrations()
