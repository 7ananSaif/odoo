"""Create or update the manager owner account.

Usage:
    python scripts/create_owner.py --email owner@example.com --name "Owner" [--password S3cret]

If --password is omitted, a strong one is generated and printed once.
2FA (TOTP) is enrolled on the owner's first browser login.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import create_all, session_scope  # noqa: E402
from app.models.user import User  # noqa: E402
from app.security import generate_token, hash_password  # noqa: E402
from app.services import permissions  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update a SaaS Manager user account.")
    parser.add_argument("--email", required=True, help="Login email")
    parser.add_argument("--name", default="SaaS Owner", help="Display name")
    parser.add_argument("--password", default="", help="Password (prompted/generated if omitted)")
    parser.add_argument("--reset-2fa", action="store_true", help="Clear the TOTP secret (re-enrol on next login)")
    parser.add_argument(
        "--role", default=None, choices=list(permissions.ROLES),
        help="Role to assign: owner, admin, operator or viewer. "
             "New accounts default to owner; existing accounts keep their role unless this is given.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    create_all()

    password = args.password
    if not password:
        try:
            first = getpass.getpass("Password (leave empty to generate): ")
        except Exception:  # noqa: BLE001 - non-interactive shell
            first = ""
        if first:
            second = getpass.getpass("Repeat password: ")
            if first != second:
                print("Passwords do not match.", file=sys.stderr)
                return 2
            password = first
        else:
            password = generate_token(12)
            print(f"Generated password: {password}")

    email = args.email.strip().lower()
    role = args.role
    with session_scope() as session:
        user = session.query(User).filter(User.email == email).one_or_none()
        created = user is None
        if user is None:
            user = User(email=email, name=args.name, password_hash=hash_password(password))
            user.apply_role(role or permissions.ROLE_OWNER)
            session.add(user)
        else:
            user.name = args.name or user.name
            user.password_hash = hash_password(password)
            user.failed_logins = 0
            user.locked_until = None
            # Only touch the role when --role was given, so a routine password
            # change never silently promotes or demotes an account.
            if role:
                user.apply_role(role)
        if args.reset_2fa:
            user.totp_secret_enc = None
            user.totp_enabled = False
        final_role = permissions.normalize_role(user.role)

    action = "created" if created else "updated"
    print(f"User {action}: {email}  [role={final_role}]")
    if args.reset_2fa:
        print("2FA reset — it will be re-enrolled on the next login.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
