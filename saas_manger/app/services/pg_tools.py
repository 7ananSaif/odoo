"""PostgreSQL admin helpers using configurable pg_dump / pg_restore / psql paths."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from app.config import settings

_logger = logging.getLogger(__name__)


class PgError(RuntimeError):
    """Raised when a PostgreSQL tool exits non-zero."""


def _env() -> dict[str, str]:
    """Build the environment (PG* variables) for the pg tools."""
    env = dict(os.environ)
    if settings.pg_password:
        env["PGPASSWORD"] = settings.pg_password
    env["PGHOST"] = settings.pg_host
    env["PGPORT"] = str(settings.pg_port)
    if settings.pg_user:
        env["PGUSER"] = settings.pg_user
    return env


def _run(cmd: list[str], *, stdin=None) -> subprocess.CompletedProcess:
    """Run a pg tool, raising PgError on failure."""
    _logger.info("pg_tools: %s", " ".join(cmd[:2]) + " ...")
    result = subprocess.run(
        cmd,
        env=_env(),
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise PgError(result.stderr.decode(errors="replace").strip() or f"exit {result.returncode}")
    return result


def backup_dir() -> Path:
    """Return (creating if needed) the backup directory."""
    path = Path(settings.backup_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_path(db_name: str, reason: str = "manual", fmt: str = "zip") -> Path:
    """Return a timestamped backup file path for a database."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    ext = "zip" if fmt == "zip" else ("dump" if fmt == "custom" else "sql")
    return backup_dir() / f"{db_name}_{reason}_{ts}.{ext}"


def db_exists(db_name: str) -> bool:
    """Return True when the database exists on the server."""
    sql = "SELECT 1 FROM pg_database WHERE datname = %s"
    try:
        result = _run([
            settings.pg_psql, "-tAc",
            f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'",
            "-d", "postgres",
        ])
    except PgError:
        # Fall back to a parametrised query is not possible with -c; keep simple.
        _logger.warning("db_exists check failed for %s", db_name)
        return False
    return result.stdout.strip() == b"1"


def create_database(db_name: str, template: str = "template0") -> None:
    """Create an empty database (owner = configured user)."""
    _run([settings.pg_psql, "-d", "postgres", "-c",
          f'CREATE DATABASE "{db_name}" ENCODING \'UTF8\' TEMPLATE {template}'])


def drop_database(db_name: str, terminate_connections: bool = True) -> None:
    """Terminate connections and drop a database."""
    if terminate_connections:
        _run([settings.pg_psql, "-d", "postgres", "-c",
              "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
              f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()"])
    _run([settings.pg_psql, "-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{db_name}"'])


def terminate_connections(db_name: str) -> None:
    """Close all connections to a database."""
    _run([settings.pg_psql, "-d", "postgres", "-c",
          "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
          f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()"])


def db_size_mb(db_name: str) -> float:
    """Return the on-disk size of a database in megabytes."""
    result = _run([settings.pg_psql, "-tAc",
                   f"SELECT pg_database_size('{db_name}')", "-d", "postgres"])
    try:
        return round(int(result.stdout.strip() or b"0") / (1024 * 1024), 2)
    except ValueError:
        return 0.0


def filestore_path(db_name: str) -> Path:
    """Return the Odoo filestore directory of a database."""
    return Path(settings.odoo_data_dir) / "filestore" / db_name


def _zip_filestore(staging: Path, db_name: str) -> None:
    """Copy the tenant filestore next to the SQL dump inside the staging dir."""
    src = filestore_path(db_name)
    if src.is_dir():
        shutil.copytree(src, staging / "filestore")


def dump_database(db_name: str, *, fmt: str = "custom", with_filestore: bool = True) -> Path:
    """Dump a database (optionally with its filestore). Returns the artefact path.

    For ``fmt='zip'`` the dump is written to a temporary directory, the filestore
    is copied alongside it, and the whole directory is zipped (Odoo-compatible).
    """
    if fmt == "zip":
        return _dump_zip(db_name, with_filestore)

    target = backup_path(db_name, fmt=fmt)
    pg_fmt = "c" if fmt == "custom" else "p"
    _run([settings.pg_dump, "--no-owner", f"--format={pg_fmt}", f"--file={target}", db_name])
    if with_filestore:
        src = filestore_path(db_name)
        if src.is_dir():
            dest = target.with_suffix(target.suffix + ".filestore")
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(src, dest)
    return target


def _dump_zip(db_name: str, with_filestore: bool) -> Path:
    import tempfile  # noqa: PLC0415

    target = backup_path(db_name, fmt="zip")
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        _run([settings.pg_dump, "--no-owner", f"--file={staging / 'dump.sql'}", db_name])
        if with_filestore:
            _zip_filestore(staging, db_name)
        # Base name without extension is required by zipfile's make_archive.
        base = str(target)[:-4]
        shutil.make_archive(base, "zip", staging)
    return target


def restore_database(db_name: str, dump_file: str) -> None:
    """Restore a dump into the (existing, empty) database ``db_name``."""
    dump_file = str(dump_file)
    if dump_file.lower().endswith(".zip"):
        _restore_zip(db_name, dump_file)
    elif dump_file.lower().endswith(".sql"):
        _run([settings.pg_psql, "-q", "-d", db_name, "-f", dump_file])
    else:
        _run([settings.pg_restore, "--no-owner", "--dbname", db_name, dump_file])


def _restore_zip(db_name: str, dump_file: str) -> None:
    import tempfile
    import zipfile  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        with zipfile.ZipFile(dump_file) as zf:
            names = zf.namelist()
            zf.extractall(staging, members=[n for n in names if n == "dump.sql" or n.startswith("filestore/")])
        sql = staging / "dump.sql"
        if sql.is_file():
            _run([settings.pg_psql, "-q", "-d", db_name, "-f", str(sql)])
        filestore = staging / "filestore"
        if filestore.is_dir():
            dest = filestore_path(db_name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            shutil.move(str(filestore), str(dest))


def duplicate_database(source: str, target: str) -> None:
    """Create ``target`` as a physical copy of ``source``."""
    terminate_connections(source)
    _run([settings.pg_psql, "-d", "postgres", "-c",
          f'CREATE DATABASE "{target}" TEMPLATE "{source}"'])
