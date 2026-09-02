"""Pydantic response/request models for the GlassBox API.

Field names mirror the JSON shapes actually returned by the legacy
Flask dashboard (backend-source/dashboard/DASHBOARD_PRO.py) so the
contract is a faithful port, not a redesign.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

Signal = Literal["BUY", "SELL", "HOLD"]


# ---- /api/data, /api/track1/data, /api/track2/data ----

class TrackDataPoint(BaseModel):
    date: str
    portfolio_value: float
    daily_return: float
    positions: Optional[int] = None
    signal: Optional[Signal] = None
    market_return: Optional[float] = None
    agents_active: Optional[int] = None
    vn_score: Optional[float] = None
    track: Optional[str] = None


# ---- /api/track1/agents, /api/track2/agents ----

class TrackAgent(BaseModel):
    name: str
    score: float
    win_rate: float
    decisions: int
    avg_impact: float
    color: str


class TrackAgentsResponse(BaseModel):
    agents: List[TrackAgent]
    vn_score: float
    total_agents: int


# ---- /api/agent-performance ----

class AgentPerformance(BaseModel):
    name: str
    score: float
    win_rate: float
    decisions: int
    avg_impact: float


# ---- /api/holdings ----

class Holding(BaseModel):
    symbol: str
    name: str
    sector: str
    weight: float
    signal: Signal
    win_rate: float
    sharpe: float
    test_return: float
    fast_ma: int
    slow_ma: int
    rsi_low: int
    rsi_high: int
    beta: float
    current_price: float
    price_change: float
    current_rsi: float
    volume: int
    data_date: str


class HoldingsSummary(BaseModel):
    total_symbols: int
    avg_win_rate: float
    best_performer: str
    best_return: float
    portfolio_beta: float
    data_source: str
    data_date: str


class HoldingsResponse(BaseModel):
    holdings: List[Holding]
    summary: HoldingsSummary
    sectors: Dict[str, float]


# ---- /api/live-signals & /ws/signals ----

class LiveSignal(BaseModel):
    symbol: str
    name: str
    sector: str
    current_price: float
    signal: Signal
    confidence: float
    rsi: float
    ma_cross: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    volume_ratio: float
    suggested_weight: float
    fast_ma: int
    slow_ma: int
    test_sharpe: float
    win_rate: float
    data_date: str


class LiveSignalsSummary(BaseModel):
    buy_signals: int
    sell_signals: int
    hold_signals: int
    avg_confidence: float
    data_source: str
    last_update: str


class LiveSignalsResponse(BaseModel):
    signals: List[LiveSignal]
    summary: LiveSignalsSummary


# ---- /api/monte-carlo ----

class MonteCarloResult(BaseModel):
    mean: float
    percentile_5: float
    percentile_95: float
    prob_profit: float
    paths: List[List[float]]
    final_values: List[float]


# ---- /api/historical-reports ----

class HistoricalReport(BaseModel):
    date: str
    file: str
    final_value: float
    return_: float = Field(alias="return")
    sharpe: float
    max_dd: float

    class Config:
        populate_by_name = True


# ---- /api/daily-summary ----

class DailySummary(BaseModel):
    status: str
    current_value: float
    daily_change: float
    vn_score: float
    risk_status: Literal["LOW", "MEDIUM", "HIGH"]
    sharpe: float
    max_dd: float
    win_rate: float
    position_util: float
    alerts: List[str]
    dates: List[str]
    growth_rates: List[float]


# ---- Agent Factory (Phase 4) ----

AgentType = Literal["deterministic", "llm"]
Provider = Literal["vllm", "ollama", "gemini", "claude"]
OrchestrationMode = Literal["sequential", "parallel", "committee_vote"]


class AgentParams(BaseModel):
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 1024
    extra: Dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    id: Optional[str] = None
    name: str
    role: str
    type: AgentType
    provider: Optional[Provider] = None
    model: Optional[str] = None
    params: AgentParams = Field(default_factory=AgentParams)
    system_prompt: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    enabled: bool = True


class OrchestrationConfig(BaseModel):
    id: Optional[str] = None
    name: str
    mode: OrchestrationMode
    agent_ids: List[str]
    coordinator: str = "vn_engine"
    schedule: Optional[str] = None
    agent_timeout_s: float = Field(30.0, description="Per-agent wall-clock budget for one run")
    run_budget_s: float = Field(120.0, description="Whole-orchestration wall-clock budget")


# ---- Provider health + call logging (Phase 5) ----

class ProviderHealth(BaseModel):
    provider: Provider
    reachable: bool
    detail: Optional[str] = None
    checked_at: str


class LLMCallLog(BaseModel):
    id: str
    agent_id: Optional[str] = None
    provider: Provider
    model: str
    started_at: str
    duration_ms: Optional[int] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    status: Literal["running", "ok", "error", "timeout"]
    error: Optional[str] = None
    estimated_cost_usd: Optional[float] = Field(
        None, description="None when the provider/model has no pricing entry (e.g. self-hosted)"
    )


# ---- Admin audit log (Phase 6) ----

class AuditLogEntry(BaseModel):
    id: str
    actor: str
    action: str = Field(..., description='e.g. "agent.create", "agent.delete", "orchestration.run", "report.generate"')
    resource_type: str = Field(..., description='"agent" | "orchestration" | "report" | "auth"')
    resource_id: Optional[str] = None
    detail: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class PaginatedAuditLog(BaseModel):
    items: List[AuditLogEntry]
    total: int


class PaginatedLLMCalls(BaseModel):
    items: List[LLMCallLog]
    total: int


# ---- Background jobs: agent test-run, orchestration run, report generate ----

JobKind = Literal["agent_test_run", "orchestration_run", "report_generate"]
JobState = Literal["queued", "running", "done", "error"]


class JobStatus(BaseModel):
    job_id: str
    kind: JobKind
    status: JobState
    created_at: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class JobAccepted(BaseModel):
    job_id: str


class AgentTestRunRequest(BaseModel):
    input: str = Field(..., description="Freeform prompt/context to run the agent against")


class OrchestrationRunRequest(BaseModel):
    input: Optional[str] = None


class ReportGenerateRequest(BaseModel):
    date: Optional[str] = Field(None, description="YYYYMMDD; defaults to the latest report on disk")
    provider: Provider = "ollama"
    model: str
    agent_id: Optional[str] = Field(None, description="Reuse an existing agent's system_prompt/params if set")


class DailyReportNarrative(BaseModel):
    id: str
    date: str
    provider: Provider
    model: str
    narrative: str
    created_at: str


# ---- Job WebSocket message envelope (/ws/jobs/{job_id}) ----
#
# All frames share this shape: {"type": ..., "data": {...}}
#   {"type": "log",    "data": {"message": str, "ts": str}}
#   {"type": "token",  "data": {"text": str}}          -- one streamed LLM output chunk
#   {"type": "status", "data": JobStatus}               -- terminal frame; socket closes after
#
# Mirrors the existing /ws/signals envelope convention ({"type", "data"})
# so both dashboards' WS clients share one parsing pattern.


# ---- Auth ----

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Literal["admin", "viewer"]


class LoginRequest(BaseModel):
    username: str
    password: str
