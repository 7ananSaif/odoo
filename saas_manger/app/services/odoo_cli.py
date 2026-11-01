"""Run the Odoo CLI (``odoo-bin``) for operations that must not go through the client UI.

The core patch treats a CLI run (``-i`` / ``-u`` / ``--reinit`` without a live
HTTP request) as owner-authorised, so the manager can drive module updates here
even when the tenant token path is not used.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.config import settings

_logger = logging.getLogger(__name__)


@dataclass
class CliResult:
    """Outcome of an Odoo CLI invocation."""

    returncode: int
    stdout: str
    stderr: str
    command: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return (self.stdout or "") + ("\n" + self.stderr if self.stderr else "")


def _base_command() -> list[str]:
    """Return the interpreter + odoo-bin prefix for this platform."""
    bin_path = settings.odoo_bin
    if settings.odoo_python:
        return [settings.odoo_python, bin_path]
    return [sys.executable, bin_path]


def _env() -> dict[str, str]:
    """Environment for the CLI (PG credentials + a marker so logs can be traced)."""
    env = dict(os.environ)
    if settings.pg_password:
        env["PGPASSWORD"] = settings.pg_password
    env["PGHOST"] = settings.pg_host
    env["PGPORT"] = str(settings.pg_port)
    if settings.pg_user:
        env["PGUSER"] = settings.pg_user
    env["SAAS_MANAGER_CLI"] = "1"
    return env


def run(
    db_name: str,
    *,
    update_modules: list[str] | None = None,
    install_modules: list[str] | None = None,
    stop_after_init: bool = True,
    log_path: str | Path | None = None,
    extra_args: list[str] | None = None,
    timeout: int | None = None,
) -> CliResult:
    """Run an Odoo CLI operation against ``db_name``.

    :param update_modules: passed with ``-u`` (comma separated). Use ``["all"]`` for everything.
    :param install_modules: passed with ``-i`` (comma separated).
    :param log_path: when given, stdout+stderr are also streamed to this file.
    """
    cmd = _base_command()
    cmd += ["-c", os.path.join(os.path.dirname(settings.odoo_bin), "odoo.conf")] if settings.odoo_bin else []
    cmd += ["-d", db_name]
    if install_modules:
        cmd += ["-i", ",".join(install_modules)]
    if update_modules:
        cmd += ["-u", ",".join(update_modules)]
    if stop_after_init:
        cmd += ["--stop-after-init"]
    cmd += extra_args or []

    _logger.info("odoo_cli: running %s", " ".join(cmd))
    started = datetime.now()
    proc = subprocess.run(
        cmd,
        env=_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    stdout = proc.stdout.decode(errors="replace")
    stderr = proc.stderr.decode(errors="replace")

    if log_path:
        target = Path(log_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(f"\n===== {started.isoformat()} :: {' '.join(cmd)} =====\n")
            fh.write(stdout)
            fh.write(stderr)

    return CliResult(returncode=proc.returncode, stdout=stdout, stderr=stderr, command=cmd)
