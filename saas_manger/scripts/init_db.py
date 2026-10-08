"""Create the manager database schema and seed the default settings.

Usage:
    python scripts/init_db.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python scripts/init_db.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.db import create_all, session_scope  # noqa: E402
from app.services import settings_service  # noqa: E402


def main() -> int:
    print(f"Database: {settings.manager_db_url.split('@')[-1]}")
    create_all()
    print("Schema created (or already present).")

    with session_scope() as session:
        settings_service.seed_defaults(session)
    print(f"Seeded {len(settings_service.DEFAULTS)} default settings.")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
