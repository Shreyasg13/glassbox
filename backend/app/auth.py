"""JWT auth with role-based access (admin vs viewer).

TODO(real-auth): the credential check below is a single hardcoded dev
account. Before Phase 6 launch this must be replaced with a real user
store (hashed passwords, multiple accounts) -- everything else here
(token issuance, decoding, the require_admin dependency) is meant to
carry over unchanged.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

SECRET_KEY = os.environ.get("GLASSBOX_JWT_SECRET", "dev-only-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12

# TODO(real-auth): replace with a real user table.
_DEV_USERS = {
    "admin": {"password": "admin", "role": "admin"},
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


class TokenPayload(BaseModel):
    sub: str
    role: Literal["admin", "viewer"]


def authenticate(username: str, password: str) -> TokenPayload | None:
    user = _DEV_USERS.get(username)
    if user is None or user["password"] != password:
        return None
    return TokenPayload(sub=username, role=user["role"])


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


async def require_admin(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
