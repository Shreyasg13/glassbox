from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .. import auth as auth_module
from .. import db
from ..models import LoginRequest, Token
from ..rate_limit import rate_limit_login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token, dependencies=[Depends(rate_limit_login)])
async def login(payload: LoginRequest):
    identity = auth_module.authenticate(payload.username, payload.password)
    if identity is None:
        # Log the attempted username for audit trails, never the password.
        db.log_audit("unknown", "auth.login_failed", "auth", None, {"username": payload.username})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = auth_module.create_access_token(identity)
    db.log_audit(identity.sub, "auth.login_success", "auth", None, {})
    return Token(access_token=token, role=identity.role)
