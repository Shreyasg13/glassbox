from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import data_source as ds
from ..models import MonteCarloResult

router = APIRouter(prefix="/api", tags=["monte-carlo"])


@router.post("/monte-carlo", response_model=MonteCarloResult)
async def api_monte_carlo(days: int = 7, simulations: int = 1000, confidence: float = 0.95):
    result = ds.run_monte_carlo(days=days, simulations=simulations, confidence=confidence)
    if result is None:
        raise HTTPException(status_code=404, detail="No data available")
    return result
