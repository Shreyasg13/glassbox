"""JWT auth with role-based access (admin vs viewer).

Account sources, in the order authenticate() checks them:
1. The bootstrap admin -- username "admin", password supplied ONLY via the
   environment (GLASSBOX_ADMIN_PASSWORD_HASH, a bcrypt hash, preferred; or
   GLASSBOX_ADMIN_PASSWORD, plain, >= MIN_ADMIN_PASSWORD_LEN chars). Unset
   means there is no admin login at all -- there is deliberately no
   built-in default. (This replaces the old hardcoded admin/admin, which
   was a live admin login on the public deployment.)
2. The opt-in dev accounts admin/admin and user/user, ONLY when
   GLASSBOX_ENABLE_DEV_USERS=1 and never when GLASSBOX_ENV=production
   (startup refuses that combination). For local development and the
   test-suite; off by default.
3. The real `users` table (app/db.py), populated via POST /auth/signup.
   Passwords are hashed with bcrypt, never stored or logged in plain
   text. "admin" and "user" are reserved usernames at signup time so a
   real signup can never collide with (or shadow) the accounts above.
4. OAuth accounts (Google for now, see oauth_login below and
   routers/oauth.py) -- also rows in the `users` table, distinguished by
   having oauth_provider/oauth_subject set and password_hash=None. Those
   accounts can never log in via the password form (authenticate() below
   guards against that explicitly).

Tokens are signed with PyJWT (python-jose was dropped: 3.3.0 carries
open CVEs -- algorithm confusion and a JWE decompression bomb -- and its
ecdsa dependency has one too, and neither is needed for plain HS256).
"""
from __future__ import annotations

import hmac
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from . import db

log = logging.getLogger("glassbox.auth")

_DEV_SECRET = "dev-only-secret-change-me"
MIN_SECRET_LEN = 32


def _is_production() -> bool:
    return os.environ.get("GLASSBOX_ENV", "development").strip().lower() == "production"


def _load_secret() -> str:
    secret = os.environ.get("GLASSBOX_JWT_SECRET", "").strip()
    if _is_production():
        if not secret or secret == _DEV_SECRET:
            # A forged-admin-token risk, not a config nicety: anyone who
            # knows the default can mint a valid admin JWT. Refuse to boot.
            raise RuntimeError(
                "GLASSBOX_JWT_SECRET is unset or still the dev default while GLASSBOX_ENV=production. "
                "Generate one with: python -m app.scripts.gen_secrets"
            )
        if os.environ.get("GLASSBOX_ENABLE_DEV_USERS") == "1":
            raise RuntimeError("GLASSBOX_ENABLE_DEV_USERS=1 is not allowed when GLASSBOX_ENV=production.")
        if len(secret) < MIN_SECRET_LEN:
            log.warning(
                "GLASSBOX_JWT_SECRET is shorter than %d characters -- rotate it (python -m app.scripts.gen_secrets).",
                MIN_SECRET_LEN,
            )
        return secret
    return secret or _DEV_SECRET


SECRET_KEY = _load_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("GLASSBOX_TOKEN_TTL_MINUTES", str(60 * 8)))

# Opt-in only -- see the module docstring. Read at call time (not import
# time) so tests can flip it with monkeypatch.setenv.
_DEV_USERS = {
    "admin": {"password": "admin", "role": "admin"},
    "user": {"password": "user", "role": "viewer"},
}

BOOTSTRAP_ADMIN_USERNAME = "admin"
MIN_ADMIN_PASSWORD_LEN = 12

# Case-insensitive -- signup already rejects "Admin"/"USER" etc. via the
# same lowercased comparison used everywhere else in this module. Also
# what routers/me.py uses to recognise accounts that have no `users` row.
RESERVED_USERNAMES = {"admin", "user"}

MIN_USERNAME_LEN = 3
MIN_PASSWORD_LEN = 10
# bcrypt only looks at the first 72 BYTES of a password and silently
# ignores the rest -- reject longer ones instead of pretending they count.
MAX_PASSWORD_BYTES = 72

# Small on purpose: a length floor plus this catches the passwords that
# get tried first in credential-stuffing runs, without shipping a wordlist.
_COMMON_PASSWORDS = {
    "password", "password1", "password12", "password123", "passw0rd123",
    "1234567890", "12345678910", "123456789012", "0123456789", "qwertyuiop",
    "qwerty12345", "qwerty123456", "1q2w3e4r5t", "iloveyou123", "letmein1234",
    "welcome123", "welcome1234", "admin12345", "administrator", "changeme123",
    "abcd123456", "abc1234567", "glassbox123", "glassbox1234",
}

# A real bcrypt hash of a throwaway string. authenticate() verifies
# against it when the username doesn't exist so "no such user" and "wrong
# password" take the same time -- otherwise response latency tells an
# attacker which usernames are registered.
_DUMMY_HASH = bcrypt.hashpw(b"glassbox-timing-equaliser", bcrypt.gensalt()).decode("ascii")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


class TokenPayload(BaseModel):
    sub: str
    role: Literal["admin", "viewer"]


class SignupError(ValueError):
    """Raised for any signup validation failure -- the router turns this
    into a 400 with the message as-is (all messages here are already
    safe to show a user, never leak internals)."""


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        # Malformed stored hash -- treat as a failed verification, not a
        # server error (should never happen since _hash_password is the
        # only writer, but a corrupt row must not become an open door).
        return False


def _dev_users_enabled() -> bool:
    return os.environ.get("GLASSBOX_ENABLE_DEV_USERS") == "1" and not _is_production()


def _check_bootstrap_admin(password: str) -> bool:
    """True iff `password` matches the env-configured admin credential.
    Prefers the bcrypt hash; falls back to the plain value (compared in
    constant time). Returns False when neither is configured, or when the
    plain value is too weak to be trusted."""
    pw_hash = os.environ.get("GLASSBOX_ADMIN_PASSWORD_HASH", "").strip()
    if pw_hash:
        return _verify_password(password, pw_hash)
    plain = os.environ.get("GLASSBOX_ADMIN_PASSWORD", "")
    if not plain:
        return False
    if len(plain) < MIN_ADMIN_PASSWORD_LEN:
        log.error("GLASSBOX_ADMIN_PASSWORD is shorter than %d characters; admin login disabled.", MIN_ADMIN_PASSWORD_LEN)
        return False
    return hmac.compare_digest(password.encode("utf-8"), plain.encode("utf-8"))


def authenticate(username: str, password: str) -> Optional[TokenPayload]:
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        # Nothing we store can match, and it caps the work an attacker can
        # make each login attempt cost.
        return None

    if username == BOOTSTRAP_ADMIN_USERNAME:
        if _check_bootstrap_admin(password):
            return TokenPayload(sub=BOOTSTRAP_ADMIN_USERNAME, role="admin")
        if not _dev_users_enabled():
            return None

    if _dev_users_enabled():
        dev_user = _DEV_USERS.get(username)
        if dev_user is not None:
            if not hmac.compare_digest(password.encode("utf-8"), dev_user["password"].encode("utf-8")):
                return None
            return TokenPayload(sub=username, role=dev_user["role"])

    row = db.get_user_by_username(username)
    # row["password_hash"] is None for OAuth-only accounts (see oauth_login)
    # -- reject rather than crash on the bcrypt call below.
    if row is None or not row.get("password_hash"):
        _verify_password(password, _DUMMY_HASH)  # equalise timing, see _DUMMY_HASH
        return None
    if not _verify_password(password, row["password_hash"]):
        return None
    return TokenPayload(sub=row["username"], role=row["role"])


def _validate_new_password(username: str, password: str) -> None:
    if len(password) < MIN_PASSWORD_LEN:
        raise SignupError(f"Password must be at least {MIN_PASSWORD_LEN} characters")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise SignupError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
    lowered = password.lower()
    if lowered in _COMMON_PASSWORDS:
        raise SignupError("That password is too common -- choose something less guessable")
    if lowered == username.lower():
        raise SignupError("Password can't be your username")


def signup(username: str, password: str) -> TokenPayload:
    """Creates a real account with role="viewer" (self-serve signup never
    grants admin -- an admin role is only ever assigned by hand, e.g.
    directly in the DB or by promoting a user via a future admin-users
    endpoint). Raises SignupError on any validation failure."""
    username = username.strip()
    if len(username) < MIN_USERNAME_LEN:
        raise SignupError(f"Username must be at least {MIN_USERNAME_LEN} characters")
    _validate_new_password(username, password)
    if username.lower() in RESERVED_USERNAMES:
        raise SignupError("That username is reserved")
    if db.get_user_by_username(username) is not None:
        raise SignupError("That username is already taken")

    row = db.create_user(
        {
            "username": username,
            "username_lower": username.lower(),
            "password_hash": _hash_password(password),
            "role": "viewer",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return TokenPayload(sub=row["username"], role=row["role"])


def oauth_login(provider: str, subject: str, email: str) -> TokenPayload:
    """Finds or creates a user for a completed OAuth exchange (called
    from routers/oauth.py after the provider confirms the identity).
    Identity is keyed on (provider, subject) -- the provider's own
    stable user id -- not on email, since email can change or be
    reused; email is only used to pick a human-readable username on
    first login. Always role="viewer", same self-serve rule as password
    signup -- an OAuth login can never grant admin either."""
    row = db.get_user_by_oauth(provider, subject)
    if row is not None:
        return TokenPayload(sub=row["username"], role=row["role"])

    username = email
    if username.lower() in RESERVED_USERNAMES or db.get_user_by_username(username) is not None:
        # Extremely unlikely (a password-signup account already claimed
        # this exact email as a username) -- disambiguate rather than
        # silently take over or crash.
        username = f"{email}+{provider}"

    row = db.create_user(
        {
            "username": username,
            "username_lower": username.lower(),
            "password_hash": None,
            "role": "viewer",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "oauth_provider": provider,
            "oauth_subject": subject,
            "email": email,
        }
    )
    return TokenPayload(sub=row["username"], role=row["role"])


def create_access_token(payload: TokenPayload) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": payload.sub,
        "role": payload.role,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    try:
        # `algorithms` is pinned to HS256 (never read from the token's own
        # header) and exp/sub are mandatory, so a token missing either is
        # rejected instead of treated as non-expiring or anonymous.
        raw = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
        return TokenPayload(sub=raw["sub"], role=raw["role"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:  # ValueError covers pydantic's ValidationError (bad role)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> TokenPayload:
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return decode_token(token)


async def get_current_user_optional(token: str | None = Depends(oauth2_scheme)) -> Optional[TokenPayload]:
    """Soft auth for endpoints that are public but personalize when a
    valid token happens to be present (e.g. /api/holdings filtering to
    the caller's own watchlist) -- returns None rather than raising on
    a missing OR invalid/expired token, since these endpoints must keep
    serving the shared/global view to anonymous demo visitors either way."""
    if token is None:
        return None
    try:
        return decode_token(token)
    except HTTPException:
        return None


async def require_admin(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
