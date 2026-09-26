"""Admin: see and change the feature flags / output kill switches (see app/flags.py)."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from .. import flags
from ..auth import TokenPayload, require_role
from ..rate_limit import rate_limit_admin_mutations

router = APIRouter(prefix="/api/admin/flags", tags=["flags"], dependencies=[Depends(rate_limit_admin_mutations)])


class FlagBody(BaseModel):
    enabled: bool


@router.get("")
async def list_flags(user: TokenPayload = Depends(require_role("admin"))) -> Dict[str, Any]:
    return {"flags": await run_in_threadpool(flags.all_flags)}


@router.post("/{key}")
async def set_flag(key: str, body: FlagBody, user: TokenPayload = Depends(require_role("admin"))) -> Dict[str, Any]:
    try:
        return await run_in_threadpool(flags.set_flag, key, body.enabled, user.sub)
    except flags.UnknownFlag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown flag") from None
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Flags are not available yet: the database migration has not been applied") from None
