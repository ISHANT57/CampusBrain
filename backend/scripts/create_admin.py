"""Create an admin account.

Students never authenticate, so there is no self-registration endpoint — this
is the only way an account comes into existence.

On the Render free tier there is no Shell tab and no Pre-Deploy Command
(both paid-only), so the deployed path is scripts/render-start.sh calling this
on boot with ADMIN_EMAIL / ADMIN_PASSWORD set in the dashboard. Run it by hand
the same way anywhere you have the backend's dependencies installed:

    python scripts/create_admin.py --email you@college.edu

Password comes from --password, else $ADMIN_PASSWORD, else an interactive
prompt. Re-running for an existing email resets that account's password, which
doubles as the password recovery there's no UI for.
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.services.user_service import UnknownOrganizationError, register_user  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    # Optional so the password can come from the environment or a prompt
    # instead of sitting in shell history and in the container's process list.
    parser.add_argument("--password", default=None)
    parser.add_argument("--org-id", type=int, default=1)
    parser.add_argument(
        "--super", action="store_true", help="create a SUPER_ADMIN instead of an ADMIN"
    )
    args = parser.parse_args()

    password = args.password or os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    if len(password) < 12:
        # No password policy exists anywhere else in this app — this account
        # is the only thing standing between the internet and the knowledge
        # base, and it's created by hand, so the floor goes here.
        print("Password must be at least 12 characters.", file=sys.stderr)
        return 1

    role = UserRole.SUPER_ADMIN if args.super else UserRole.ADMIN
    db = SessionLocal()
    try:
        existing = (
            db.query(User).filter(User.org_id == args.org_id, User.email == args.email).first()
        )
        if existing is not None:
            existing.hashed_password = hash_password(password)
            existing.role = role
            db.commit()
            print(f"Updated {args.email} (org {args.org_id}) — role {role.value}.")
            return 0

        user = register_user(
            db, org_id=args.org_id, email=args.email, password=password, role=role
        )
        print(f"Created {user.email} (org {user.org_id}, id {user.id}) — role {role.value}.")
        return 0
    except UnknownOrganizationError:
        print(
            f"Organization {args.org_id} does not exist — run `alembic upgrade head` first "
            "(migration b3e1f0a72c44 seeds org 1).",
            file=sys.stderr,
        )
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
