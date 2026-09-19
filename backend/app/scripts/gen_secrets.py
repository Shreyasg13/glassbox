"""Generates the secrets the backend needs, so nobody has to invent them.

    python -m app.scripts.gen_secrets                 # new JWT signing secret
    python -m app.scripts.gen_secrets --admin         # + prompt for the admin
                                                      #   password, print its bcrypt hash

Prints lines to paste into the deployment's .env. Nothing is written to disk
and nothing is logged. In docker:
    docker compose run --rm backend python -m app.scripts.gen_secrets --admin

Note on the hash: a bcrypt hash contains `$` characters, which docker compose
would try to interpolate inside an unquoted .env value -- so the line printed
here is wrapped in single quotes. Keep them.
"""
from __future__ import annotations

import argparse
import getpass
import secrets
import sys

from .. import auth


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--admin", action="store_true", help="also hash an admin password (prompted, not echoed)")
    args = parser.parse_args()

    print(f"GLASSBOX_JWT_SECRET={secrets.token_hex(32)}")

    if args.admin:
        password = getpass.getpass("Admin password (min %d chars): " % auth.MIN_ADMIN_PASSWORD_LEN)
        if len(password) < auth.MIN_ADMIN_PASSWORD_LEN:
            print(f"error: admin password must be at least {auth.MIN_ADMIN_PASSWORD_LEN} characters", file=sys.stderr)
            return 1
        if len(password.encode("utf-8")) > auth.MAX_PASSWORD_BYTES:
            print(f"error: admin password must be at most {auth.MAX_PASSWORD_BYTES} bytes", file=sys.stderr)
            return 1
        if getpass.getpass("Repeat it: ") != password:
            print("error: passwords didn't match", file=sys.stderr)
            return 1
        print(f"GLASSBOX_ADMIN_PASSWORD_HASH='{auth._hash_password(password)}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
