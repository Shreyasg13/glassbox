"""JWT auth with role-based access (admin vs viewer).

Three account sources:
1. `_DEV_USERS` -- the original hardcoded admin/admin and user/user
   accounts. Kept unconditionally (not gated behind an env var) since
   this deployment's docs (README, DEPLOY_GCP.md, PROJECT_STATUS.md)
   all point people at these exact credentials as the known way in --
   removing them would silently break every one of those instructions.
2. The real `users` table (app/db.py), populated via POST /auth/signup.
   Passwords are hashed with bcrypt, never stored or logged in plain
   text. "admin" and "user" are reserved usernames at signup time
   specifically so a real signup can never collide with (and
   confusingly shadow, or be shadowed by) the two dev accounts above.
3. OAuth accounts (Google for now, see oauth_login below and
   routers/oauth.py) -- also rows in the `users` table, distinguished by
   having oauth_provider/oauth_subject set and password_hash=None. Those
   accounts can never log in via the password form (authenticate() below
   guards against that explicitly).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from . import db

SECRET_KEY = os.environ.get("GLASSBOX_JWT_SECRET", "dev-only-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12

_DEV_USERS = {
    "admin": {"password": "admin", "role": "admin"},
    "user": {"password": "user", "role": "viewer"},
}

# Case-insensitive -- signup already rejects "Admin"/"USER" etc. via the
# same lowercased comparison used everywhere else in this module.
RESERVED_USERNAMES = {"admin", "user"}

MIN_USERNAME_LEN = 3
MIN_PASSWORD_LEN = 6

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


def authenticate(username: str, password: str) -> Optional[TokenPayload]:
    dev_user = _DEV_USERS.get(username)
    if dev_user is not None:
        if dev_user["password"] != password:
            return None
        return TokenPayload(sub=username, role=dev_user["role"])

    row = db.get_user_by_username(username)
    # row["password_hash"] is None for OAuth-only accounts (see oauth_login)
    # -- reject rather than crash on the bcrypt call below.
    if row is None or not row.get("password_hash") or not _verify_password(password, row["password_hash"]):
        return None
    return TokenPayload(sub=row["username"], role=row["role"])


def signup(username: str, password: str) -> TokenPayload:
    """Creates a real account with role="viewer" (self-serve signup never
    grants admin -- an admin role is only ever assigned by hand, e.g.
    directly in the DB or by promoting a user via a future admin-users
    endpoint). Raises SignupError on any validation failure."""
    username = username.strip()
    if len(username) < MIN_USERNAME_LEN:
        raise SignupError(f"Username must be at least {MIN_USERNAME_LEN} characters")
    if len(password) < MIN_PASSWORD_LEN:
        raise SignupError(f"Password must be at least {MIN_PASSWORD_LEN} characters")
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
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": payload.sub, "role": payload.role, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    try:
        raw = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload(sub=raw["sub"], role=raw["role"])
    except (JWTError, KeyError) as exc:
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
