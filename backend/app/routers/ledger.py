"""Admin: verify the append-only hash-chained call ledger (S3 T11)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .. import ledger
from ..auth import TokenPayload, require_role
from ..rate_limit import rate_limit_admin_mutations

router = APIRouter(
    prefix="/api/admin/ledger",
    tags=["ledger"],
    dependencies=[Depends(require_role("admin")), Depends(rate_limit_admin_mutations)],
)


class LedgerRow(BaseModel):
    seq: int
    call_id: str
    ticker: str
    call_type: str
    recorded_at: str
    hash: str


class VerifyResponse(BaseModel):
    ok: bool
    rows: int
    first_bad_seq: Optional[int]
    reason: str


@router.get("", response_model=List[LedgerRow])
async def list_ledger(
    from_seq: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
) -> List[LedgerRow]:
    """List ledger entries (metadata only, no payload)."""
    rows = ledger.read(from_seq=from_seq, limit=limit)
    return [LedgerRow(**r) for r in rows]


@router.post("/verify", response_model=VerifyResponse)
async def verify_ledger() -> VerifyResponse:
    """Recompute the hash chain from seq 1 and report the first broken link."""
    return VerifyResponse(**ledger.verify())